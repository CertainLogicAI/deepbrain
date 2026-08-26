# DeepBrain Beta — Quickstart

## What is it?

A browser-based coding agent with a proprietary execution memory. You type what you want. It generates code, runs it in a sandbox, verifies it works, and shows you the result. If it's a pattern the system has stored before, it can return the cached solution.

## How to connect

**URL:** http://[server-ip]:8081
**No login required.** Open the URL in Chrome or Firefox.

## How it works

```
[Chat] Type: "write a fibonacci function"
  → Timechain check (proprietary execution memory)
  → DeepSeek generates code (local, runs on CPU)
  → Executes in sandbox, exit 0, prints 120
  → Shows you the code + output
  → Seals successful execution back to the chain
```

## What it can do

- **Generate code** from natural language descriptions
- **Execute code** in a sandbox (Python, JS, Shell)
- **Edit code** in the Monaco editor (syntax highlighting, auto-complete)
- **Run your own code** — click the "Run" button or Ctrl+Enter
- **Remember patterns** — cached solutions are stored for reuse

## What it can't do (yet)

- No user accounts or auth (coming with Stripe)
- No persistent storage of your sessions
- No Docker sandbox (uses direct subprocess for now)
- Limited to Python, JavaScript, and Shell execution
- DeepSeek runs on CPU — slower than GPU for large generations

## Beta-specific notes

- **Everything is free during beta.** No credit card needed.
- **Your code is executed on our server.** Don't run anything you wouldn't on your own machine.
- **No rate limits.** Use it as much as you want.
- **Feedback:** Send issues to Anton directly. Every bug report makes it better.

## Current limitations

- DeepSeek-Coder-V2-Lite 16B (Q4) — runs on CPU, ~5-15s per generation
- Falls back to Flash (OpenRouter) if DeepSeek fails
- Timechain replay — cache hit rate available under NDA
- 120s timeout for generation + execution

## Tech stack

```
Browser (Monaco editor + terminal) ← SSE → DeepBrain server (Flask/Gunicorn)
  ├── Timechain API (proprietary execution memory)
  ├── DeepSeek-Coder-V2-Lite 16B (Ollama, CPU)
  └── Flash (OpenRouter, fallback)
```

## Licensing

DeepBrain is licensed under **Business Source License 1.1** (see `LICENSE`).

The framework code is free for:
- Non-production evaluation and testing
- Personal and educational use
- Organizations with ≤3 employees and <$100K revenue

Commercial use beyond those limits requires a license from CertainLogic.

**The model:** We make money on model quality, not framework gatekeeping.
The agent framework is open under BSL. The value is in the models, timechain
memory, and routing infrastructure behind it.

## Pricing (post-beta)

- **Free tier:** Local DeepSeek in your browser (WebGPU/WASM) — coming soon
- **$200/mo:** Unlimited — server-side generation, timechain, premium routing