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

A four-condition HumanEval+ benchmark runner is at **`evaluation/run_deepbrain_eval.py`**.

| Condition | What It Does | Current Score (DeepSeek V4 Flash) |
|---|---|---|
| A. Cold, no memory (80% of eval) | LLM baseline on 131 cold-split tasks | 115/131 code gen; pass@1: **0.659/0.640** (base/plus); subset: 0.94/0.913 |
| B. Memory on, empty chain (held-out 20%) | Empty cache — measures raw holdout quality | 29/33 code gen; pass@1: **0.177/0.165**; subset: 1.0/0.933 |
| C. Sibling-coded memory | **Exploratory only.** Seeds held-out tasks with unrelated generated functions. Not a product claim. | — |
| D. Exact replay of sealed tasks | Generate → test → seal only plus-passers → reset chain → replay | 101/131 sealed pass; **101/101 replay match**; code identical; EvalPlus pass@1: **0.616/0.616**; subset: 1.0/1.0 |

**Key insight, condition D:** On HumanEval+ cold-split tasks, DeepSeek V4 Flash produced 101/131 plus-passing solutions. Those 101 were sealed into timechain lite. After resetting the chain, replay returned the identical code 101/101, and EvalPlus plus-status stayed pass on all 101. Official pass@1 on the 164-task denominator is 0.616 because 63 tasks were not in the replay file.

- **Contamination is measured, not solved.** A records 115 stored prompts (cold only, 0 from held-out). B records 29 stored prompts (held-out only, 0 from cold). D records 101 stored prompts (cold only).
- **C is not a headline.** Sibling transfer does not produce non-trivial held-out lift in this harness. It remains a research path.
- All conditions scored via EvalPlus test execution (pass@1), not code-existence checks. Publishes JSONL of all solutions, meta with per-task results, contamination overlap list, and both official denominator and submitted-denominator rates.

Run it yourself:

```bash
export OPENROUTER_API_KEY="..."
cd evaluation
python3 run_deepbrain_eval.py
# Output: eval_out/solutions_*.jsonl + eval_out/full_report.json
```

**Previous bug-fix history (commit `07fd2d6`):**
- pass@1 parser now reads the correct line (was reading base as plus and vice versa)
- A/B/C/D report **n_submitted** and **subset_base/subset_plus** alongside official pass@1
- D now runs all 131 cold tasks (was running cold[:smoke] = 0)
- Contamination checks all 164 tasks (was checking tasks[:smoke] = 0)
- C excluded from headline rate as exploratory
- D checks per-task `plus_status` from `_eval_results.json` (not aggregate pass@1 which is always 1/164 for a 1-real-163-empty file)

## License

**BSL 1.1** — Business Source License. Free for evaluation, personal, and small-organizational use. Changes to Apache 2.0 in 2029. The models DeepBrain routes to are independently owned and licensed.

## Honest Limitations

- **Memory**: stored cases are deterministic. Novel cases still go to an LLM. Guardrails reduce *cached* fabrication but do not eliminate LLM hallucination on new problems.
- **Sandbox**: the current execution path is `python3 -c`, `node -e`, `bash -c` with a 30s timeout and output truncation. No seccomp, no network policy, no filesystem jail in the live path. BETA.md documents this. Docker/seccomp isolation is a commercial add-on.
- **Timechain lite**: uses SHA3-256 (not Keccak-256), linear scan retrieval, 2000/5000 char truncation on prompts/code. Documented in `timechain/README.md`.
- **Eval**: A/B produce per-submit and full-denominator rates. D tests then seals: 101/131 cold tasks sealed pass on DeepSeek V4 Flash, 101/101 replay match. No claim of lift on novel tasks — memory is a cache, not a reasoner. C is exploratory, not a product claim.

---

## Traced data sample

One real, delivered record with its full provenance chain — inspectable and independently
verifiable from the file alone: [`samples/`](./samples/).

It shows the derivation rule end to end: raw source line → `sha256(normalize(sig(record)))` →
canonical record. One record, not a corpus. The hashes in it are recomputable from the
published bytes; if they match, the rule is honest.

---

Built by **CertainLogic** — deterministic AI infrastructure.

Proof, not promises.
