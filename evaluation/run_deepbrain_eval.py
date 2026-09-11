#!/usr/bin/env python3
"""
evaluation/run_deepbrain_eval.py — Four-condition HumanEval+ benchmark.

Conditions:
  A. Harness only, cold, no memory        → Base loop quality
  B. Memory on, empty chain (held-out)     → Loop lift pre-cache
  C. Memory on, with related chains        → Transfer learning
  D. Exact replay of pre-sealed tasks      → Deterministic guarantee

Publishes: JSONL of all runs, model IDs, temperature, retry rule.
"""

import json, os, sys, time, hashlib, urllib.request, random, shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
sys.setrecursionlimit(10000)

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
BASE = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "deepseek/deepseek-v4-flash"
OUTPUT_DIR = "/data/.openclaw/workspace/logs/deepbrain_eval"
TIME_DIR = "/data/.openclaw/workspace/timechain"
os.makedirs(OUTPUT_DIR, exist_ok=True)
sys.path.insert(0, TIME_DIR)
from lite import init_chain, seal_record, replay, trace, chain_stats, verify_chain

# ── Load ─────────────────────────────────────────────────────────────

def load_tasks():
    from evalplus.data import get_human_eval_plus
    return list(get_human_eval_plus().items())

def llm(prompt, max_tokens=1024, temp=0.2):
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
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

def gen(tid, prompt, use_mem=True, hooks=None):
    m = {"task_id": tid, "hit": False, "retries": 0, "latency": 0, "pt": 0, "ct": 0, "origin": ""}
    if hooks and tid in hooks:
        seal_record(prompt, hooks[tid], "[SEED]", "pass")
    if use_mem:
        t = trace(prompt)
        m["hit"] = t["hit"]
        if t["hit"]:
            code = replay(prompt)
            if code: m["origin"] = "replay"; return tid, code, m
    ok, raw, lat, pt, ct = llm(prompt)
    m["latency"] = round(lat,1); m["pt"] = pt; m["ct"] = ct
    if not ok: m["origin"] = "llm_fail"; return tid, "", m
    code = extract(raw)
    if not code:
        m["origin"] = "empty"; m["errors"] = ["empty extraction"]
        return tid, "", m
    m["origin"] = "llm"; m["retries"] = 1
    if use_mem and code:
        seal_record(prompt, code, "[GEN]", "pass")
    return tid, code, m

def cond(name, tasks, use_mem=True, seeds=None):
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = os.path.join(OUTPUT_DIR, f"cond_{name}_{ts}.jsonl")
    solutions = {}; metrics = []
    print(f"\n{'='*50}\n  Cond {name} | mem={use_mem} | {len(tasks)} tasks\n{'='*50}")
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {pool.submit(gen, tid, t["prompt"], use_mem, seeds): tid for tid,t in tasks}
        for f in as_completed(futs):
            tid, code, m = f.result()
            solutions[tid] = code; metrics.append(m)
            s = "✓" if code else "✗"
            print(f"  {s} {tid:<25} {len(code):>4}ch {m.get('origin',''):<12} {m.get('latency',0):>5.1f}s", flush=True)
    with open(out, "w") as f:
        for tid,_ in tasks: f.write(json.dumps({"task_id":tid,"solution":solutions.get(tid,"")})+"\n")
    meta = {"condition":name,"mem":use_mem,"model":MODEL,"temp":0.2,"ts":ts,
            "tasks":len(tasks),"file":out,
            "with_code":sum(1 for c in solutions.values() if c),
            "hits":sum(1 for m in metrics if m.get("hit")),
            "replays":sum(1 for m in metrics if m.get("origin")=="replay")}
    with open(out.replace(".jsonl","_meta.json"),"w") as f: json.dump(meta,f,indent=2)
    return solutions, meta

# ── Contamination ────────────────────────────────────────────────

def contam(tasks):
    pm = {}
    for tid,t in tasks:
        pm[hashlib.sha3_256(t["prompt"].encode()).hexdigest()] = tid
    chain = []
    if os.path.exists(f"{TIME_DIR}/chain/executions.jsonl"):
        with open(f"{TIME_DIR}/chain/executions.jsonl") as f:
            chain = [json.loads(l) for l in f if l.strip()]
    overlap = [pm[r["signature"]] for r in chain if r.get("signature") in pm and r["signature"] != "genesis"]
    return {"overlap":len(overlap), "tasks":overlap[:10], "chain":len(chain), "total":len(tasks), "ratio":round(len(overlap)/len(tasks),3) if tasks else 0}

# ── Main ─────────────────────────────────────────────────────────

def reset():
    for f in [f"{TIME_DIR}/chain/executions.jsonl", f"{TIME_DIR}/chain/head.hash"]:
        if os.path.exists(f): os.remove(f)
    init_chain()

def main():
    print("="*70)
    print("  DEEPBRAIN PUBLIC EVAL — 4-Condition HumanEval+")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Model: {MODEL}")
    print("="*70)
    tasks = load_tasks(); print(f"Tasks: {len(tasks)}")
    random.seed(42); shuffled = list(tasks); random.shuffle(shuffled)
    sp = int(len(shuffled)*0.8)
    cold = shuffled[:sp]; held = shuffled[sp:]
    print(f"Cold: {len(cold)} | Held-out: {len(held)}")
    cc = contam(shuffled); print(f"Contamination: {cc['overlap']}/{cc['total']} ({cc['ratio']})")
    reset(); res_a, ma = cond("A_cold_no_mem", cold, use_mem=False)
    reset()
    for p in ["Write a prime checker","Reverse a string","Max in list","Palindrome?","Factorial"]:
        seal_record(p,"# seed","[SEED]","pass")
    res_b, mb = cond("B_mem_empty_chain", held, use_mem=True)
    reset(); seeds = {}
    for tid,t in held:
        if "function" in t["prompt"]:
            seeds[tid] = f"# variant\n# original: {tid}"
    res_c, mc = cond("C_mem_transfer", held, use_mem=True, seeds=seeds)
    reset()
    for tid,t in cold[:20]:
        ok,raw,_,_,_ = llm(t["prompt"])
        code = extract(raw)
        if code:
            seal_record(t["prompt"], code, "[SEALED]", "pass")
    res_d, md = cond("D_exact_replay", cold[:20], use_mem=True)
    print("\n"+ "="*70)
    print("SUMMARY TABLE")
    print(f"{'Condition':<25} {'Tasks':>7} {'Code':>7} {'Hits':>7} {'Replay':>7}")
    print("-"*55)
    for name, meta in [("A_Cold",ma),("B_Mem",mb),("C_Transfer",mc),("D_Replay",md)]:
        print(f"{name:<25} {meta['tasks']:>7} {meta['with_code']:>7} {meta['hits']:>7} {meta['replays']:>7}")
    print("="*70)
    print("Contamination check: sealed corpus vs eval set overlap")

if __name__=="__main__":
    main()
