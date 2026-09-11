#!/usr/bin/env python3
"""
evaluation/run_deepbrain_eval.py — Four-condition HumanEval+ benchmark.

Scored by EvalPlus test execution. Publishes JSONL + meta JSON + EvalPlus results.

Conditions:
  A. Cold, no memory (80% of eval)       → Base codegen quality
  B. Memory on, empty chain (held-out)   → Loop lift pre-cache
  C. [EXPLORATORY] Sibling-then-memory   → Transfer experiments (not a headline)
  D. Test-then-Seal-then-Replay          → Deterministic guarantee

Usage:
  OPENROUTER_API_KEY="sk-..." python3 evaluation/run_deepbrain_eval.py [--smoke N]
"""

import json, os, sys, time, hashlib, urllib.request, random, shutil, tempfile, io, contextlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
sys.setrecursionlimit(10000)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
CHAIN_DIR = os.path.join(BASE_DIR, "..", "timechain", "chain")
OUT_DIR = os.path.join(BASE_DIR, "eval_out")
os.makedirs(OUT_DIR, exist_ok=True)
sys.path.insert(0, os.path.join(BASE_DIR, "..", "timechain"))
from lite import init_chain, seal_record, replay, trace, chain_stats, verify_chain
API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
BASE = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "deepseek/deepseek-v4-flash"

ALL_TASKS = []  # filled by main() — full 164-task list
tasks_by_id = {}  # task_id -> task_data for D's replay phase


def load_tasks():
    from evalplus.data import get_human_eval_plus
    return list(get_human_eval_plus().items())


def llm(prompt, max_tokens=1024, temp=0.2):
    payload = {"model": MODEL, "messages": [{"role":"user","content":prompt}],
               "max_tokens": max_tokens, "temperature": temp}
    req = urllib.request.Request(BASE, json.dumps(payload).encode(), {
        "Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json",
        "HTTP-Referer": "https://certainlogic.ai/deepbrain-eval"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
        return (True, d["choices"][0]["message"]["content"] or "",
                time.time()-t0, d.get("usage",{}).get("prompt_tokens",0),
                d.get("usage",{}).get("completion_tokens",0))
    except Exception as e:
        return (False, str(e)[:200], time.time()-t0, 0, 0)


def extract(raw):
    if not raw: return ""
    code = raw
    for tag in ["```python", "```py", "```"]:
        if tag in code:
            s = code.index(tag) + len(tag)
            e = code.index("```", s) if "```" in code[s:] else len(code)
            code = code[s:e].strip()
            break
    return code.strip()


def score_solutions(sol_path, label, n_submitted=None):
    """Run EvalPlus evaluate, capture stdout, parse pass@1.
    Returns dict with pass@1_base, pass@1_plus (official rate = passes/164)
    and subset_base, subset_plus (passes/n_submitted) when n_submitted given."""
    from evalplus.evaluate import evaluate
    f = io.StringIO()
    stdout = ""
    try:
        with contextlib.redirect_stdout(f):
            evaluate(dataset="humaneval", samples=sol_path, parallel=4,
                     i_just_wanna_run=True, test_details=True)
        stdout = f.getvalue()
    except Exception as e:
        return {"error": str(e), "stdout": stdout}

    # EvalPlus stdout format:
    # humaneval (base tests)
    # pass@1:\t0.659
    # humaneval+ (base + extra tests)
    # pass@1:\t0.640
    base = None; plus = None
    last_header = ""
    for line in stdout.split("\n"):
        ls = line.strip()
        if "humaneval+" in ls.lower():
            last_header = "plus"
        elif ("humaneval" in ls.lower() or "base tests" in ls.lower()) and "human+" not in ls.lower():
            last_header = "base"
        if "pass@1" in ls.lower():
            parts = ls.split()
            try:
                val = float(parts[-1])
                if last_header == "plus":
                    plus = val
                else:
                    base = val
            except:
                pass

    result = {"pass@1_base": base, "pass@1_plus": plus, "stdout": stdout}
    if n_submitted and n_submitted > 0:
        if base is not None:
            result["subset_base"] = round(base * 164 / n_submitted, 3)
        if plus is not None:
            result["subset_plus"] = round(plus * 164 / n_submitted, 3)
        result["n_submitted"] = n_submitted
    return result


def gen(task_id, prompt, use_mem=True, seed_code=None):
    meta = {"task_id": task_id, "hit": False, "retries": 0, "latency": 0,
            "pt": 0, "ct": 0, "origin": ""}
    if seed_code:
        seal_record(prompt, seed_code, "[SIBLING]", "pass")
    if use_mem:
        t = trace(prompt)
        meta["hit"] = t["hit"]
        if t["hit"]:
            code = replay(prompt)
            if code:
                meta["origin"] = "replay"
                return task_id, code, meta
    ok, raw, lat, pt, ct = llm(prompt)
    meta["latency"] = round(lat, 1); meta["pt"] = pt; meta["ct"] = ct
    if not ok: meta["origin"] = "llm_fail"; return task_id, "", meta
    code = extract(raw)
    if not code: meta["origin"] = "empty"; return task_id, "", meta
    meta["origin"] = "llm"; meta["retries"] = 1
    if use_mem and code:
        seal_record(prompt, code, "[GENERATED]", "pass")
    return task_id, code, meta


def cond(label, tasks, use_mem=True, seed_codes=None):
    solutions = {}; metrics = []
    print(f"\n{'='*60}\n  Cond {label} | mem={use_mem} | {len(tasks)} tasks\n{'='*60}")
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {pool.submit(gen, tid, t["prompt"], use_mem,
                            seed_codes.get(tid,None) if seed_codes else None): tid
                for tid,t in tasks}
        for f in as_completed(futs):
            tid = futs[f]; tid2, code, m = f.result()
            solutions[tid2] = code; metrics.append(m)
            s = "✓" if code else "✗"
            print(f"  {s} {tid2:<25} {len(code):>4}ch {m.get('origin',''):<12} {m.get('latency',0):>5.1f}s", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    sol = os.path.join(OUT_DIR, f"solutions_{label}_{ts}.jsonl")
    n_submitted = sum(1 for c in solutions.values() if c)
    with open(sol, "w") as f:
        for tid, _ in ALL_TASKS:
            f.write(json.dumps({"task_id": tid, "solution": solutions.get(tid, "")}) + "\n")
    score = None
    if n_submitted > 0:
        print("\n  Scoring...")
        score = score_solutions(sol, label, n_submitted)
    mo = {"condition": label, "mem": use_mem, "model": MODEL, "temp": 0.2, "ts": ts,
          "tasks_assigned": len(tasks), "n_submitted": n_submitted,
          "file": sol,
          "gen": {"code": sum(1 for c in solutions.values() if c),
                  "empty": sum(1 for c in solutions.values() if not c),
                  "hits": sum(1 for m in metrics if m.get("hit")),
                  "replays": sum(1 for m in metrics if m.get("origin") == "replay")},
          "eval": score}
    with open(sol.replace(".jsonl", "_meta.json"), "w") as f:
        json.dump(mo, f, indent=2)
    return solutions, mo, sol


def cond_d(label, tasks):
    """Phase 1: generate + test each. Seal only plus-passers.
       Phase 2: reset chain, replay sealed-pass prompts, score replay."""
    print(f"\n{'='*60}\n  Cond D: test-then-seal | {len(tasks)} tasks\n{'='*60}")
    sealed_pass = {}
    for tid, td in tasks:
        p = td["prompt"]
        ok, raw, _, _, _ = llm(p)
        code = extract(raw) if ok else ""
        if not code:
            print(f"  \u2717 {tid:<25} empty \u2014 skip", flush=True)
            continue
        tmp = os.path.join(OUT_DIR, f"_dt_{tid.replace('/','_')}.jsonl")
        with open(tmp, "w") as f:
            for t2, _ in ALL_TASKS:
                f.write(json.dumps({"task_id": t2, "solution": code if t2 == tid else ""}) + "\n")
        try:
            sc = score_solutions(tmp, f"_dt_{tid.replace('/','_')}")
            passed = sc and sc.get("pass@1_plus") == 1.0
        except Exception:
            passed = False
        if passed:
            sealed_pass[tid] = code
        print(f"  {'\u2713' if passed else '\u2717'} {tid:<25} \u2192 {'PASS' if passed else 'FAIL'}", flush=True)
        if os.path.exists(tmp):
            os.unlink(tmp)

    print(f"\n  Sealed: {len(sealed_pass)} pass, {len(tasks)-len(sealed_pass)} fail")

    print("\n  Phase 2: replay from sealed-pass chain...")
    reset()
    for tid, code in sealed_pass.items():
        seal_record(tasks_by_id[tid]["prompt"], code, "[PASS]", "pass")

    solutions = {}
    for tid, td in tasks:
        t = trace(td["prompt"])
        if t["hit"]:
            c = replay(td["prompt"])
            if c:
                solutions[tid] = c
                match = "match" if c == sealed_pass.get(tid, "") else "different"
                print(f"  \u21BA {tid:<25} replay ({match})", flush=True)
                continue
        solutions[tid] = ""
        print(f"  \u2717 {tid:<25} miss", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    sol = os.path.join(OUT_DIR, f"solutions_{label}_{ts}.jsonl")
    n_submitted = sum(1 for c in solutions.values() if c)
    with open(sol, "w") as f:
        for tid, _ in ALL_TASKS:
            f.write(json.dumps({"task_id": tid, "solution": solutions.get(tid, "")}) + "\n")
    score = None
    if n_submitted > 0:
        score = score_solutions(sol, label, n_submitted)
    mo = {"condition": label, "mem": True, "model": MODEL, "temp": 0.2, "ts": ts,
          "tasks_assigned": len(tasks), "n_submitted": n_submitted,
          "file": sol, "sealed_pass": len(sealed_pass),
          "sealed_fail": len(tasks) - len(sealed_pass),
          "gen": {"code": sum(1 for c in solutions.values() if c),
                  "empty": sum(1 for c in solutions.values() if not c),
                  "replays": sum(1 for tid, __ in tasks if solutions.get(tid, ""))},
          "eval": score}
    with open(sol.replace(".jsonl", "_meta.json"), "w") as f:
        json.dump(mo, f, indent=2)
    return solutions, mo, sol


def contam(tasks):
    pm = {hashlib.sha3_256(t["prompt"].encode()).hexdigest(): tid for tid, t in tasks}
    chain_path = os.path.join(CHAIN_DIR, "executions.jsonl")
    ov = []
    if os.path.exists(chain_path):
        with open(chain_path) as f:
            for line in f:
                r = json.loads(line.strip())
                s = r.get("signature", "")
                if s in pm and s != "genesis":
                    ov.append(pm[s])
    return {"overlap": len(ov), "tasks": ov[:10], "total": len(tasks),
            "ratio": round(len(ov)/len(tasks), 3) if tasks else 0}


def reset():
    for f in ["executions.jsonl", "head.hash"]:
        p = os.path.join(CHAIN_DIR, f)
        if os.path.exists(p):
            os.remove(p)
    init_chain()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="DeepBrain 4-condition HumanEval+ eval")
    parser.add_argument("--smoke", type=int, default=0, help="Limit tasks per condition")
    parser.add_argument("--only-d", action="store_true", help="Run only D condition")
    args, _ = parser.parse_known_args()
    smoke = args.smoke if args.smoke else 0

    print("="*70)
    print(f"  DEEPBRAIN EVAL \u2014 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Model: {MODEL}")
    if smoke:
        print(f"  Smoke: {smoke} tasks/condition")
    print("="*70)

    tasks = load_tasks()
    globals()["ALL_TASKS"] = list(tasks)
    globals()["tasks_by_id"] = dict(tasks)
    print(f"Tasks: {len(tasks)}")
    random.seed(42)
    shuffled = list(tasks)
    random.shuffle(shuffled)
    sp = int(len(shuffled) * 0.8)
    cold = shuffled[:sp]
    held = shuffled[sp:]

    if smoke:
        cold = cold[:smoke]
        held = held[:smoke]

    print(f"Cold (80%): {len(cold)} | Held-out (20%): {len(held)}")

    if args.only_d:
        # Reuse existing A eval_out results; run only D
        print("  --only-d: running D condition from A's cold split...")
        reset()
        res_d, md, _ = cond_d("D_replay", cold)
        cc = contam(tasks)
        print(f"\n  Contamination: {cc['overlap']}/{cc['total']} ({cc['ratio']})")
        print("\n"+"="*70)
        print("D ONLY SUMMARY")
        rpt = os.path.join(OUT_DIR, "full_report_d_only.json")
        with open(rpt, "w") as f:
            json.dump({"ts": datetime.now(timezone.utc).isoformat(), "model": MODEL,
                        "D": md, "contamination": cc}, f, indent=2)
        print(f"Report: {rpt}")
        return

    # A: cold, no memory
    reset()
    res_a, ma, _ = cond("A_cold", cold, use_mem=False)

    # B: memory on, empty chain
    reset()
    res_b, mb, _ = cond("B_mem_empty", held, use_mem=True)

    # C: exploratory — sibling-then-memory
    reset()
    seeds = {}
    for tid, td in held:
        sp = f"Write a function related to this (slightly different): {td['prompt'][:200]}"
        ok, raw, _, _, _ = llm(sp)
        c = extract(raw) if ok else None
        if c:
            seeds[tid] = c
    print(f"\n  Siblings generated: {len(seeds)}/{len(held)}")
    res_c, mc, _ = cond("C_mem_sibling", held, use_mem=True, seed_codes=seeds)

    # D: test-then-seal-then-replay on ALL cold tasks
    reset()
    res_d, md, _ = cond_d("D_replay", cold)

    # Contamination over ALL 164 tasks
    cc = contam(tasks)
    print(f"\n  Contamination: {cc['overlap']}/{cc['total']} ({cc['ratio']})")

    print("\n"+"="*70)
    print("SUMMARY")
    hdr = f"{'Condition':<22} {'Tasks':>6} {'Code':>5} {'Sub':>5} {'base@1':>8} {'+@1':>8} {'sub_ba':>7} {'sub_pl':>7}"
    print(hdr)
    print("-"*72)
    for nm, m in [("A_cold", ma), ("B_empty", mb), ("C_sibling", mc), ("D_replay", md)]:
        g = m.get("gen", {}); e = m.get("eval", {}) or {}
        b = e.get("pass@1_base", "?"); p = e.get("pass@1_plus", "?")
        sb = e.get("subset_base", "?"); sp = e.get("subset_plus", "?")
        nsub = e.get("n_submitted", m.get("n_submitted", "?"))
        print(f"{nm:<22} {m['tasks_assigned']:>6} {g.get('code',0):>5} {nsub:>5} {str(b):>8} {str(p):>8} {str(sb):>7} {str(sp):>7}")
    print("="*70)
    rpt = os.path.join(OUT_DIR, "full_report.json")
    with open(rpt, "w") as f:
        json.dump({"ts": datetime.now(timezone.utc).isoformat(), "model": MODEL,
                    "conditions": {"A": ma, "B": mb, "C": mc, "D": md},
                    "contamination": cc}, f, indent=2)
    print(f"Report: {rpt}")

if __name__ == "__main__":
    main()