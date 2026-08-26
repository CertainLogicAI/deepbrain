# DeepBrain — Browser-Based Agent Framework

A browser-based coding agent framework with **timechain memory, multi-model routing, and sandbox execution**. Types what you want → generates code → runs it in a sandbox → verifies it works → remembers the solution.

**License:** BSL 1.1 (see [LICENSE](LICENSE))

---

## What It Is

DeepBrain is an agent framework that routes requests through:

- **Timechain memory** — 75K+ proven execution traces. If it's a pattern solved before, it returns the proven solution instantly.
- **Multi-model routing** — routes to the best model for the task (Flash, Qwen 3.6, DeepSeek, Kimi, local)
- **Cognitive engine** — sensory loop, contradiction detection, freshness decay, trust calibration
- **Sandbox execution** — runs code in isolated environment, captures output, verifies results
- **Safety layer** — dedup, circuit breakers, rate limiters, injection defenses

## Quick Start

```bash
git clone https://github.com/CertainLogicAI/deepbrain.git
cd deepbrain
pip3 install flask gunicorn
bash start.sh
# Opens at http://127.0.0.1:8081
```

## License

**BSL 1.1 — Business Source License**

- Free for evaluation, personal use, educational use
- Free for organizations ≤3 employees and <$100K revenue
- Changes to Apache 2.0 in 2029

The framework code is BSL licensed. The models DeepBrain routes to (Flash, Qwen, DeepSeek, Kimi, etc.) are independently owned and licensed by their respective providers.

## Why BSL

We make money on model quality — not gatekeeping the framework. The agent scaffold is the loss leader. The value is in the LLMs behind it.

---

Built by **CertainLogic** — deterministic AI infrastructure.