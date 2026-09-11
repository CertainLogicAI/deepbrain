# DeepBrain — Browser-Based Coding Agent

A local Flask/Gunicorn app with a Monaco editor UI. Type a request → generate code → run it in a subprocess → store what worked for replay.

**What this repo is:** The harness. The agent scaffold. Works offline from clone.

**What this repo is not:** A solved-hallucination system, a production sandbox, or a finished cognitive architecture. See [Honest Limitations](#honest-limitations) below.

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

## Architecture (What Ships Here)

The clone-and-run path is a three-stage loop:

1. **Guard (Qwen 3.6)** — cheap local/api model decides EXECUTE / REFUSE / ESCALATE
2. **Code generation** — OpenRouter (default Flash, falls back to DeepSeek/Kimi/local) produces code from your prompt
3. **Execution** — subprocess with 30s timeout captures output. Not Docker/seccomp. See BETA.md.

Passing results are stored in a local NDJSON log.

## Timechain Memory

This repo includes **`timechain/lite.py`** — a zero-dependency local execution log that works 100% offline:

```bash
python3 timechain/lite.py stats
python3 timechain/lite.py seal --prompt "..." --code "..." --result "[PASS]" --verdict pass
python3 timechain/lite.py replay --prompt "..."
python3 timechain/lite.py trace --prompt "..."
python3 timechain/lite.py verify
```

- Hash-linked records (SHA256), append-only, verifiable
- Deterministic replay: same prompt returns stored solution without an LLM call
- Retrieval by Keccak-256 prompt signature (uses SHA3-256 — see limitations in the README)
- Linear scan retrieval — fine for small chains, production uses the commercial ring store

The protocol + full documentation are at `timechain/README.md`.

## Evaluation

A four-condition HumanEval+ benchmark runner is at **`evaluation/run_deepbrain_eval.py`**:

| Condition | What It Measures |
|---|---|
| A. Cold, no memory (80% of eval) | Base loop quality |
| B. Memory on, empty chain (held-out 20%) | Loop lift before any cache |
| C. Memory on, sibling solutions seeded | Transfer learning from non-identical prompts |
| D. Exact replay of sealed tasks | Deterministic guarantee |

Scored by EvalPlus test execution (pass@1), not by code-exists checks. Publishes JSONL of all solutions, meta with per-task results, and contamination ratio.

Run it yourself:

```bash
export OPENROUTER_API_KEY="..."
cd evaluation
python3 run_deepbrain_eval.py
# Output: eval_out/solutions_*.jsonl + eval_out/*_meta.json
```

## License

**BSL 1.1** — Business Source License. Free for evaluation, personal, and small-organizational use. Changes to Apache 2.0 in 2029. The models DeepBrain routes to are independently owned and licensed.

## Honest Limitations

- **Memory**: stored cases are deterministic. Novel cases still go to an LLM. Guardrails reduce *cached* fabrication but do not eliminate LLM hallucination on new problems.
- **Sandbox**: the current execution path is `python3 -c`, `node -e`, `bash -c` with a 30s timeout and output truncation. No seccomp, no network policy, no filesystem jail in the live path. BETA.md documents this. Docker/seccomp isolation is a commercial add-on.
- **Timechain lite**: uses SHA3-256 (not Keccak-256), linear scan retrieval, 2000/5000 char truncation on prompts/code. Documented in `timechain/README.md`.
- **Eval**: the four-condition runner is a scaffold that scores via real EvalPlus test execution. The commercial tier provides additional ring-store scale, distributed consensus, and production sandbox isolation.

---

Built by **CertainLogic** — deterministic AI infrastructure.

Proof, not promises.
