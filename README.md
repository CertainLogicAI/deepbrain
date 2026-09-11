# DeepBrain — Browser-Based Coding Agent

**What this is:** A local Flask/Gunicorn app with a Monaco editor UI. You type a request, it generates code, runs it, and stores what worked.

**What this is not:** A solved-hallucination system, a production sandbox, or a finished cognitive architecture. The public repo is the harness. The claims in the README below match the code you can run.

---

## Quick Start

```bash
git clone https://github.com/CertainLogicAI/deepbrain.git
cd deepbrain
pip3 install flask gunicorn
bash start.sh
# Opens at http://127.0.0.1:8081
```

---

## Architecture (What Ships in This Repo)

The clone-and-run path is a three-stage loop:

1. **Guard/Qwen 3.6** — a cheap local or API model that decides EXECUTE / REFUSE / ESCALATE
2. **Code generation** — OpenRouter (default Flash, falls back to DeepSeek/Kimi/local) produces code from your prompt
3. **Execution** — a subprocess with a 30s timeout runs the code and captures output. Not Docker/seccomp in the live path. See BETA.md for the honest safety story.

If execution passes, the result is stored in a local NDJSON execution log.

That loop is it. The cognitive orchestration topics below (sensor polling, trust tiers, kill-switch, action dedup) are lightweight modules in the `cognition/` and `safety/` folders.

## The Commercial Product (Not in This Repo)

The value-add layer that runs on top of this harness:

- **Timechain** — an append-only ring store with 75K+ sealed execution records, signature-based retrieval, and verified hit-rate data that lifts codegen on *novel* (not cached) problems. This repository contains a stub client. The protocol is documented at `timechain/lite.py` in the [CertainLogicAI org repo](https://github.com/CertainLogicAI) — that module works 100% offline with a local JSONL chain.
- **Distributed sandbox** — seccomp + optional Docker isolation for multi-user or exposed deployments.
- **HumanEval+ benchmark** — we publish a four-condition split (cold, memory-empty, memory-transfer, exact-replay) in the `evaluation/` directory of the org repo. Read the methodology before extrapolating any headline number.

## Key Design Notes

### Memory / Replay
The timechain stores *exact match* prompts and their verified solutions. For stored problems, the system returns a deterministic answer without calling an LLM. For novel problems, it still calls an LLM — the same way any agent harness does. "Stored cases are deterministic; novel cases still go to an LLM" is the accurate framing.

### Sandbox
The current execution path is `python3 -c`, `node -e`, `bash -c` with a 30s timeout and stdout/stderr truncation. That is a subprocess with a timeout — not a sandbox. No seccomp, no network policy, no filesystem jail in the live path. Fine on your laptop for code you would run anyway. BETA.md explains this honestly. Docker/seccomp isolation is available in the commercial tier.

### Multi-Model Routing
Real but simple: guard (cheap) → escalate to Flash/DeepSeek/Kimi/local. Useful cost control. Not a learned router or a replacement for frontier models.

## Benchmark Data

We publish a four-condition HumanEval+ eval alongside this project. The conditions are:

| Condition | What It Measures |
|---|---|
| Harness only, cold, no memory | Base loop quality on 80% of HumanEval+ |
| Memory on, empty chain (held-out 20%) | Does the loop help before any cache exists? |
| Memory on, with related sealed problems | Transfer learning (non-identical, similar prompts) |
| Exact replay of pre-sealed tasks | Deterministic guarantee on stored problems |

The JSONL of all runs, exact model IDs, temperature, and retry rules are published alongside. Run the eval yourself with `python3 evaluation/run_deepbrain_eval.py`.

## License

**BSL 1.1 — Business Source License**

- Free for evaluation, personal use, educational use
- Free for organizations ≤3 employees and <$100K revenue
- Changes to Apache 2.0 in 2029

The framework code is BSL licensed. The models DeepBrain routes to are independently owned and licensed.

## Why BSL

We make money on the memory system, not the harness. The agent scaffold is the loss leader. The value is in the execution corpus that lifts new problems — and that corpus is what stays private.

## Honest Limitations

- The "timechain" in this repo is a client to an external memory service. The protocol is documented in the org repo's `timechain/lite.py`.
- The sandbox is a subprocess with a timeout. Docker isolation ships separately.
- Guardrails reduce *cached* fabrication but do not eliminate LLM hallucination on novel codegen.
- The "cognitive engine" vocabulary is heavier than the algorithms.

---

Built by **CertainLogic** — deterministic AI infrastructure.

Proof, not promises.