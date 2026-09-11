# Timechain Lite — Local Execution Memory Protocol

A standalone, zero-dependency append-only execution log with hash-linked records. Designed to be verifiable, portable, and evaluable without any external service.

## Quick Start

```bash
# Initialize (creates ./chain/ with genesis block)
python3 lite.py stats

# Seal an execution record
python3 lite.py seal --prompt "Write a prime checker" --code "def is_prime..." --result "[PASS]" --verdict pass

# Replay a stored solution (no LLM call)
python3 lite.py replay --prompt "Write a prime checker"

# Trace a query (hit/miss/refuse)
python3 lite.py trace --prompt "Write a prime checker"

# Verify chain integrity
python3 lite.py verify

# Chain statistics
python3 lite.py stats
```

## Protocol

### Record Structure
```json
{
  "signature": "keccak256(prompt)",          // deterministic query id
  "prev_hash": "sha256(previous_record)",    // chain link
  "hash": "sha256(this_record, excl hash)",  // seal
  "prompt": "...",
  "code": "...",
  "result": "...",
  "verdict": "pass|fail|refuse|skip",
  "ts": 1234567890
}
```

### Guarantees
- **Append-only**: once sealed, no deletes or edits
- **Hash-linked**: each record references the previous record's hash
- **Deterministic replay**: same prompt → same signature → same stored code (if sealed)
- **Verifiable**: `verify` command walks the chain and recomputes every hash

## Python API

```python
from lite import *

# Seal a record
seal_record(prompt="...", code="...", result="...", verdict="pass")

# Replay (stored solution, no LLM)
code = replay("Write a function to...")

# Trace
result = trace("Some query")
# → {"hit": True, "verdict": "pass", ...}

# Chain integrity
violations = verify_chain()  # empty = valid

# Stats
stats = chain_stats()  # total, sealed, failures, refusals, chain_length
```

## Design Notes

- **2000 char prompt truncation**: storage efficiency. The signature covers the full original.
- **No deletes**: sealing is permanent. If a record is wrong, seal a correction (it gets a new hash).
- **No external API**: everything works offline from a repo clone.

## License

BSL 1.1 — same as the parent DeepBrain project. This module is freely usable, modifiable, and forkable for non-production use. Production use requires a commercial license.