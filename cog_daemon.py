"""
deepbrain/cog_daemon.py — Persistent cognitive sensory daemon.

License: BSL 1.1 (see LICENSE in this directory)
CertainLogic <anton@certainlogic.ai> — (c) 2026

Runs the sense → dissonance → tier → act → seal loop in a continuous cycle.

DISARMED by default:
    - Kill switch file exists at startup → daemon exits immediately
    - All thresholds set to "stop"
    - No actions registered
    - Trust model = all untrusted

To arm:
    1. Configure stream trust levels
    2. Set dissonance tiers
    3. Enable action plugins
    4. Delete kill switch file (/tmp/deepbrain-safe)
    5. Start daemon with --run flag
"""

import argparse
import logging
import os
import signal
import sys
import time
from pathlib import Path

from deepbrain.safety.governor import get_governor, Governor
from deepbrain.safety.trust import register as trust_register, profile as trust_profile, is_armed
from deepbrain.safety.dedup import get_dedup
from deepbrain.cognition.engine import CognitiveEngine
from deepbrain.actions.base import get_all as all_actions, execute as execute_action
from deepbrain.actions.plugins import init as init_actions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cog_daemon")


class CogDaemon:
    """The persistent perceptual cycle."""

    def __init__(self, governor: Governor | None = None):
        self._gov = governor or get_governor()
        self._engine = CognitiveEngine(self._gov)
        self._running = False
        self._cycle_count = 0
        self._sensors: list = []
        self._silence_monitors: dict[str, object] = {}
        self._heartbeat: object | None = None
        self._recalibration_interval = 604800  # 7 days

        # Register default sensors (all DISARMED by default — manual connect needed)
        self._register_default_sensors()

    # ── Sensor setup ────────────────────────────────────────────────

    def _register_default_sensors(self):
        from deepbrain.sensors.market import MarketPriceSensor, OrderbookSensor
        from deepbrain.sensors.logs import ErrorRateSensor, HeartbeatSensor
        from deepbrain.sensors.ecosystem import WebhookSensor, SilenceSensor

        # Stream trust is set by configuration, not hard-coded.
        # All default to "untrusted" until configured.

        mkt_price = MarketPriceSensor()
        orderbook = OrderbookSensor()
        err_rate = ErrorRateSensor()
        hb = HeartbeatSensor()
        webhook = WebhookSensor()
        silence_price = SilenceSensor(target_sensor_name="market_price", expected_interval=5.0)
        silence_logs = SilenceSensor(target_sensor_name="system_logs", expected_interval=30.0)

        self._sensors = [mkt_price, orderbook, err_rate, hb, webhook, silence_price, silence_logs]
        self._heartbeat = hb

        self._silence_monitors = {
            "market_price": silence_price,
            "system_logs": silence_logs,
        }

    # ── The perceptual cycle ────────────────────────────────────────

    def _collect_senses(self) -> dict[str, float]:
        """Poll all sensors and collect their sense events."""
        senses: dict[str, float] = {}
        stream_meta: dict[str, str] = {}

        for sensor in self._sensors:
            try:
                event = sensor.poll()
            except Exception as e:
                logger.error(f"Sensor {sensor.stream_name} poll failed: {e}")
                continue

            if event is not None:
                senses[event.sense_type] = max(senses.get(event.sense_type, 0.0), event.intensity)
                stream_meta[event.sense_type] = event.stream_name

                # Notify silence monitors
                if event.stream_name in self._silence_monitors:
                    self._silence_monitors[event.stream_name].mark_data()

        return senses

    def _act(self, profile):
        """Execute actions based on the cognitive profile's tier."""
        tier = profile.tier

        if tier == "stop":
            logger.info(f"Dissonance {profile.dissonance:.1f}: Full stop — no action")
            return

        if tier == "escalate":
            execute_action("escalate", {
                "reason": f"Dissonance {profile.dissonance:.1f} exceeds threshold",
                "profile": profile.to_dict(),
            })
            return

        # Check dedup before executing
        dedup = get_dedup()
        action_payload = profile.action_payload
        action_name = action_payload.get("action", "alert")

        if dedup.is_in_flight(profile.to_dict(), action_name):
            logger.info(f"Action '{action_name}' already in flight for this profile — skipping")
            return

        dedup.mark_in_flight(profile.to_dict(), action_name)

        try:
            result = execute_action(action_name, action_payload)
            if result:
                dedup.resolve(profile.to_dict(), action_name, "success" if result.success else "fail")
                logger.info(f"Action '{action_name}': {'success' if result.success else 'fail'} — {result.details[:100]}")
            else:
                dedup.resolve(profile.to_dict(), action_name, "no_handler")
                logger.warning(f"No action handler for '{action_name}'")
        except Exception as e:
            dedup.resolve(profile.to_dict(), action_name, f"error: {e}")
            logger.error(f"Action '{action_name}' error: {e}")

    def _seal_profile(self, profile):
        """Seal the cognitive profile outcome to the timechain.

        DISARMED: Stub. Real seal logic connects to Timechain API.
        """
        import json
        seal_path = Path("/data/.openclaw/workspace/data/cognitive-cycle-log.ndjson")
        try:
            with open(seal_path, "a") as f:
                f.write(json.dumps(profile.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Seal to NDJSON failed: {e}")
        # TODO: POST to Timechain API at 127.0.0.1:8080/seal in v2

    def _check_recalibration(self):
        """Run drift detection check (weekly)."""
        if self._cycle_count % max(1, self._recalibration_interval // 5) == 0 and self._cycle_count > 0:
            logger.info("Recalibration cycle triggered (stub)")
            # TODO: compute current metrics, compare to baseline, flag if drifted

    # ── Main loop ───────────────────────────────────────────────────

    def run_once(self):
        """Run one perceptual cycle. Returns the cognitive profile."""
        self._cycle_count += 1

        # 1. Global kill switch check
        if self._gov.global_disarmed():
            logger.warning("Kill switch active — perceptual cycle blocked")
            return None

        # 2. Collect senses
        senses = self._collect_senses()
        if not senses:
            return None  # nothing to perceive

        # 3. Get stream trust metadata
        stream_meta = {}
        for sensor in self._sensors:
            # We need mapping from sensor to its sense types — simplified for now
            sense_type = getattr(sensor, "sense_type", None)
            if sense_type and sense_type in senses:
                stream_meta[sense_type] = sensor.stream_name

        # 4. Run cognitive engine
        profile = self._engine.cycle(senses, stream_meta=stream_meta)

        # 5. Check stream trust for action permission
        trust_ok = True
        for sense_name, stream_name in stream_meta.items():
            p = trust_profile(stream_name)
            is_alert = profile.tier == "alert" or profile.action_payload.get("action") == "alert"
            if not is_alert and not p.allows_auto_execute:
                logger.info(f"Stream '{stream_name}' (trust={p.level}) doesn't allow auto-execute — rerouting to alert")
                profile.tier = "escalate"
                profile.dissonance = max(profile.dissonance, 70.0)
                trust_ok = False

        if trust_ok:
            # 6. Execute action
            self._act(profile)

        # 7. Seal outcome
        self._seal_profile(profile)

        # 8. Check recalibration
        self._check_recalibration()

        return profile

    def run_forever(self, cycle_interval: float = 5.0):
        """Run perceptual cycles indefinitely (every N seconds)."""
        if self._gov.global_disarmed():
            logger.fatal("Kill switch ACTIVE at startup — daemon will not run. To arm: rm /tmp/deepbrain-safe")
            sys.exit(0)

        self._running = True
        logger.info(f"Cognitive daemon starting (cycle={cycle_interval}s)")
        logger.info(f"  Streams: {len(self._sensors)}")
        logger.info(f"  Kill switch: {'DISARMED' if self._gov.global_disarmed() else 'ARMED'}")
        logger.info(f"  Tiers: {self._gov._tiers}")

        try:
            while self._running:
                try:
                    self.run_once()
                except Exception as e:
                    logger.exception(f"Cycle {self._cycle_count} failed: {e}")
                time.sleep(cycle_interval)
        except KeyboardInterrupt:
            logger.info("Shutdown signal received")
            self._running = False

    def stop(self):
        self._running = False


# ── CLI Entrypoint ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Cognitive Stream Daemon")
    parser.add_argument("--run", action="store_true",
                        help="Actually start the daemon (without this, just validates config)")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Perceptual cycle interval in seconds")
    args = parser.parse_args()

    # Init action plugins
    init_actions()

    gov = get_governor()

    logger.info("=== Cognitive Stream Architecture Daemon ===")
    logger.info(f"Kill switch: {'SAFE (file exists)' if gov.global_disarmed() else 'ARMED (no kill switch)'}")
    logger.info(f"Dissonance tiers: {gov._tiers}")
    logger.info(f"Configured actions: {[a.action_name for a in all_actions()]}")

    if not args.run:
        logger.info("DRY RUN — pass --run to start the daemon")
        return

    daemon = CogDaemon(governor=gov)
    daemon.run_forever(cycle_interval=args.interval)


if __name__ == "__main__":
    main()