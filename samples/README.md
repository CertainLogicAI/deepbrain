# Traced Data Sample — ds-001

One real, delivered record with its full provenance chain. This is **one record**, not a corpus.
Published so the hashing rule is independently checkable from this file alone.

## What it is
A `knowledge_fact` record captured by our pipeline, deduplicated, and emitted to the canonical set.

| Field | Value |
|---|---|
| record_type | `knowledge_fact` |
| content_type | `knowledge` |
| delivered_at | `2026-09-11T17:54:56-0400` |
| source_bucket | `data/distilled-from-tmp/brain_facts.jsonl` |
| canonical_content_sha256 | `c20eb43142ad598aede00c11efad434418c71c60da89395e3668e320e2beec96` |

## The chain

```
[hop 1] raw source line   data/distilled-from-tmp/brain_facts.jsonl : line 1
          raw sha256       2e236df3f091af6ffb0c1279a9ca3d20b6bc433ad52b1dae61db5f045df8982f
              |
              v
[hop 2] dedup rule        sha256( normalize( sig(record) ) )
          content sha256   c20eb43142ad598aede00c11efad434418c71c60da89395e3668e320e2beec96
              |
              v
[hop 3] canonical output  data/canonical-blueprint/knowledge.jsonl.gz
          recomputed sha   c20eb43142ad598aede00c11efad434418c71c60da89395e3668e320e2beec96   == hop 2  (MATCH)
```

## Reproduce it yourself (from this file only)

`data-sample-001.json` contains the record verbatim in two forms: the parsed object (`record`)
and the exact source bytes (`raw_source_line`).

```python
import json, hashlib
s = json.load(open("data-sample-001.json"))
sha = lambda b: hashlib.sha256(b).hexdigest()

# hop 1 — hash the exact source line
print(sha(s["raw_source_line"].strip().encode()))
# -> 2e236df3f091af6ffb0c1279a9ca3d20b6bc433ad52b1dae61db5f045df8982f

# hop 2 — the dedup rule
def sig(r):
    for a, b in (("content","role"),("prompt","response"),("query","response"),
                 ("instruction","output"),("input","output"),
                 ("solution","completion"),("question","answer")):
        if a in r or b in r:
            return str(r.get(a,"")) + "\x1f" + str(r.get(b,""))
    return json.dumps(r, sort_keys=True)
norm = lambda x: " ".join(x.split())
print(sha(norm(sig(s["record"])).encode()))
# -> c20eb43142ad598aede00c11efad434418c71c60da89395e3668e320e2beec96
```

Both lines must equal the values in the table above.

## Honest limits
- **One record.** This proves the hashing/derivation rule, not corpus size or quality.
- **No seal hop** here: timechain seals *execution* traces, not knowledge facts.
- **Dedup kept first-seen.** `copies_in_source_file = 1`; cross-bucket duplicate counting for this
  record is in the audit report, not recomputed in this sample.
- Redacted: this record contains no secrets, keys, balances, or personal identifiers.
