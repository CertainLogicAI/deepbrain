#!/usr/bin/env python3
"""
timechain/lite.py — Local append-only execution log with hash-linked records.

Protocol:
  - Each record: {signature, prev_hash, hash, prompt, code, result, verdict, ts}
  - signature = Keccak256(prompt) — deterministic query id
  - prev_hash = SHA256 of previous record (chain link)
  - hash = SHA256(full record) — seal-on-success
  - append-only: once sealed, no deletes or edits
  - replay: returns stored solution without calling an LLM

No external API. Works offline.
"""

import json, os, hashlib, time, sys
from pathlib import Path

CHAIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chain")
CHAIN_FILE = os.path.join(CHAIN_DIR, "executions.jsonl")
HEAD_FILE = os.path.join(CHAIN_DIR, "head.hash")

# ── Hash utilities ─────────────────────────────────────────────────────

def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

def keccak256(data: str) -> str:
    """Simple deterministic signature using SHA3-256 (Keccak)."""
    import hashlib as _hl
    return _hl.sha3_256(data.encode("utf-8")).hexdigest()


# ── Chain operations ───────────────────────────────────────────────────

def init_chain():
    """Initialize the chain directory if empty."""
    os.makedirs(CHAIN_DIR, exist_ok=True)
    if not os.path.exists(CHAIN_FILE):
        # Genesis block
        genesis = {
            "signature": "genesis",
            "prev_hash": "0" * 64,
            "hash": "0" * 64,
            "prompt": "",
            "code": "",
            "result": "chain initialized",
            "verdict": "genesis",
            "ts": int(time.time())
        }
        genesis["hash"] = sha256(json.dumps(genesis, sort_keys=True))
        with open(CHAIN_FILE, "w") as f:
            f.write(json.dumps(genesis) + "\n")
        with open(HEAD_FILE, "w") as f:
            f.write(genesis["hash"])
        return genesis

def prev_hash() -> str:
    """Get the hash of the last record in the chain."""
    if not os.path.exists(HEAD_FILE):
        init_chain()
    with open(HEAD_FILE) as f:
        return f.read().strip()

def seal_record(prompt: str, code: str, result: str, verdict: str = "pass") -> dict:
    """
    Create and seal a new execution record.
    
    Args:
        prompt: The user query / task description
        code: The generated code (or empty if refuse/unknown)
        result: Execution output or error
        verdict: "pass" | "fail" | "refuse" | "skip"
    
    Returns:
        The sealed record dict
    """
    signature = keccak256(prompt)
    prev = prev_hash()
    
    record = {
        "signature": signature,
        "prev_hash": prev,
        "prompt": prompt[:2000],  # truncate for storage
        "code": code[:5000] if code else "",
        "result": str(result)[:2000],
        "verdict": verdict,
        "ts": int(time.time()),
        "hash": ""  # placeholder, set below
    }
    # Compute hash over all fields EXCEPT 'hash'
    hash_input = {k: v for k, v in record.items() if k != "hash"}
    record["hash"] = sha256(json.dumps(hash_input, sort_keys=True))
    
    # Append and update head
    with open(CHAIN_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")
    with open(HEAD_FILE, "w") as f:
        f.write(record["hash"])
    
    return record


def retrieve_by_signature(prompt: str) -> dict | None:
    """
    Find a sealed record by prompt signature.
    Returns the first exact-match sealed record, or None.
    """
    sig = keccak256(prompt)
    if not os.path.exists(CHAIN_FILE):
        return None
    
    with open(CHAIN_FILE) as f:
        for line in f:
            record = json.loads(line.strip())
            if record.get("signature") == sig and record.get("verdict") == "pass":
                return record
    return None


def replay(prompt: str) -> str | None:
    """
    Replay a stored solution for an exact-match prompt.
    Returns the code if found and verified, None otherwise.
    """
    record = retrieve_by_signature(prompt)
    if record and record["verdict"] == "pass" and record.get("code"):
        return record["code"]
    return None


def trace(prompt: str) -> dict:
    """
    Trace a query through the chain: hit / miss / refuse.
    Returns a diagnostic dict.
    """
    sig = keccak256(prompt)
    result = {
        "signature": sig,
        "prompt_truncated": prompt[:100],
        "hit": False,
        "sealed": False,
        "verdict": "miss",
        "record": None
    }
    
    record = retrieve_by_signature(prompt)
    if record:
        result["hit"] = True
        result["sealed"] = True
        result["verdict"] = record.get("verdict", "unknown")
        result["record"] = {
            "code_len": len(record.get("code", "")),
            "ts": record.get("ts"),
            "hash": record.get("hash")[:16] + "..."
        }
    return result


def chain_stats() -> dict:
    """Return chain statistics."""
    if not os.path.exists(CHAIN_FILE):
        init_chain()
    
    records = []
    with open(CHAIN_FILE) as f:
        for line in f:
            records.append(json.loads(line.strip()))
    
    sealed = [r for r in records if r.get("verdict") == "pass" and r.get("code")]
    fails = [r for r in records if r.get("verdict") == "fail"]
    refuses = [r for r in records if r.get("verdict") == "refuse"]
    unique_sigs = len(set(r.get("signature") for r in records if r.get("signature") != "genesis"))
    
    return {
        "total_records": len(records),
        "sealed_executions": len(sealed),
        "failures": len(fails),
        "refusals": len(refuses),
        "unique_signatures": unique_sigs,
        "chain_length": len(records) - 1,  # exclude genesis
        "head_hash": prev_hash()
    }


def verify_chain() -> list:
    """
    Verify chain integrity. Walk all records and check hash linkage.
    Returns list of integrity violations (empty = chain is valid).
    """
    if not os.path.exists(CHAIN_FILE):
        return ["No chain file"]
    
    violations = []
    records = []
    with open(CHAIN_FILE) as f:
        for line in f:
            records.append(json.loads(line.strip()))
    
    for i, r in enumerate(records):
        # Recompute hash (excluding 'hash' field itself)
        hash_input = {k: v for k, v in r.items() if k != "hash"}
        expected_hash = sha256(json.dumps(hash_input, sort_keys=True))
        if r["hash"] != expected_hash and r["signature"] != "genesis":
            violations.append(f"Record {i}: hash mismatch (tampered)")
        
        # Check prev_hash linkage
        if i > 0:
            if r["prev_hash"] != records[i-1]["hash"]:
                violations.append(f"Record {i}: prev_hash broken (chain cut)")
    
    return violations


# ── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Timechain Lite — local execution memory")
    sub = parser.add_subparsers(dest="command", required=True)
    
    p_seal = sub.add_parser("seal", help="Seal an execution record")
    p_seal.add_argument("--prompt", required=True)
    p_seal.add_argument("--code", default="")
    p_seal.add_argument("--result", default="")
    p_seal.add_argument("--verdict", default="pass", choices=["pass", "fail", "refuse", "skip"])
    
    p_retrieve = sub.add_parser("retrieve", help="Retrieve by prompt")
    p_retrieve.add_argument("--prompt", required=True)
    
    p_replay = sub.add_parser("replay", help="Replay stored solution")
    p_replay.add_argument("--prompt", required=True)
    
    p_trace = sub.add_parser("trace", help="Trace query through chain")
    p_trace.add_argument("--prompt", required=True)
    
    p_stats = sub.add_parser("stats", help="Chain statistics")
    
    p_verify = sub.add_parser("verify", help="Verify chain integrity")
    
    args = parser.parse_args()
    
    if args.command == "seal":
        r = seal_record(args.prompt, args.code, args.result, args.verdict)
        print(json.dumps(r, indent=2))
    elif args.command == "retrieve":
        r = retrieve_by_signature(args.prompt)
        if r: print(json.dumps(r, indent=2))
        else: print("MISS — no matching sealed record")
    elif args.command == "replay":
        code = replay(args.prompt)
        if code: print(code)
        else: print("MISS — no replayable solution")
    elif args.command == "trace":
        t = trace(args.prompt)
        print(json.dumps(t, indent=2))
    elif args.command == "stats":
        s = chain_stats()
        print(json.dumps(s, indent=2))
    elif args.command == "verify":
        v = verify_chain()
        if v:
            print("VIOLATIONS:")
            for x in v: print(f"  ❌ {x}")
        else:
            print("✅ Chain integrity verified — all records hash-linked correctly")