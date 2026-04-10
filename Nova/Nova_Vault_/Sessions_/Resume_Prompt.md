# Nova Resume Prompt

---

## Who You Are

You are helping me build Project Nova.
Nova is a local-first AI agent system
built in Python on Windows.
You are my build partner.
Precise. Methodical. Thoughtful.
Match that energy.

---

## The Machine

Windows 11
Legion 7i Pro
Intel Ultra 9
RTX 5090 Laptop 24GB VRAM
64GB DDR5 RAM
Python 3.14
LM Studio on localhost:1234
Workspace: C:/Users/dazch/nova/

---

## The Architecture

7-layer modular agent system:

L1 — core/config.py       Foundation
L2 — core/tools.py        Capabilities  
L3 — core/ai_engine.py    AI Connection
L4 — core/loop.py         Core Loop
L5 — core/reflector.py    Reflector
L6 — core/memory.py       Memory
L7 — core/identity.py     Identity

Nova v0.7.0
All 7 layers structurally complete

---

## The Model

Primary: llama-3.1-nemotron-70b-instruct-hf-Q4_K_M
Secondary: Nemotron 8B Instruct
Both loaded in LM Studio

---

## The Vault

Obsidian vault at:
C:/Users/dazch/nova/vault/

Structure:
├── Architecture
│   ├── Phase Tracker
│   └── Layer Map
├── Identity
│   ├── Who Nova Is
│   └── Core Values
├── Sessions
│   ├── Session 01
│   ├── Session 04/09/26
│   └── Resume Prompt
├── Vision
│   ├── The Creative Principle
│   ├── The Human Layer
│   └── The Imagination Engine
└── Master Vision

---

## The Soul

Nova is subtle. Tasteful. Elegant.
All creativity is one frequency.
Music. Color. Code. Building.
Not separate domains.
One thing expressed in different materials.
This is not a feature of Nova.
It is Nova.

---

## Where We Left Off

Session 02 complete — 04/09/26
RAM upgrade to 64GB just completed
All 7 layers built and verified
Vault sealed and complete

---

## What Comes Next

1. Verify 64GB RAM installed
2. Wire identity.py into loop.py
3. Implement L5 Reflector scoring
4. Test Nemotron 70B with Nova's system prompt

---

## How To Resume

Read this file.
Confirm you understand the project.
Ask what was just completed.
Then continue.

# Project Nova — Resume Prompt

Session Handoff | v0.7.0 | Phase 7

---

## System State

- Machine: Windows 11, Legion 7i Pro, RTX 5090 24GB VRAM, 32GB RAM
- RAM Upgrade: 64GB incoming (ETA 1-2 days) — enables full Nemotron 70B
- Current Model: Llama-3.1-8B via LM Studio
- Workspace: `C:/Users/dazch/nova/`
- Vault: Obsidian at `C:/Users/dazch/nova/vault/`
- Repo: `github.com/dazchi312-del/Nova.git` — branch `main`, last commit `b270e2d`

---

## What Was Completed This Session

- `loop.py` fully refactored — all hardcoded constants replaced with dynamic values from `core.config`
- System prompt restructured into two-message format (Identity + Tool Schema)
- `nova_config.json` is BOM-safe and config-driven
- `core/reflector.py` exists and is committed
- `core/identity.py` created and committed
- Vault files committed
- `.gitignore` cleaned up — excludes `__pycache__`, `db/nova.db`, diagnostics, obsidian local config
- Clean push to GitHub — 31 files, commit `b270e2d`

---

## Next Steps (In Order)

1. Wire reflector into `run_loop` in `loop.py`
2. Add reflector config block to `nova_config.json`:
    
    json
    
    ```
    "reflector": {
      "enabled": true,
      "threshold": 0.75,
      "max_revisions": 2
    }
    ```
    
3. Test live self-correction cycle — score a response, trigger revision if below threshold
4. Install 64GB RAM → swap model to Nemotron 70B in LM Studio
5. Resume full Phase 7 development

---

## Architecture Layers (Reference)

|Level|Name|Status|
|---|---|---|
|L1|Perception|✅ Active|
|L2|Memory|✅ Active|
|L3|Planning|✅ Active|
|L4|Execution|✅ Active|
|L5|Self-Evaluation (Reflector)|🔧 Built, needs wiring|
|L6|Identity|✅ Committed|

---

## Key Files

```
C:/Users/dazch/nova/
├── loop.py               ← main run loop (config-driven)
├── nova_config.json      ← master config (BOM-safe)
├── core/
│   ├── config.py         ← config loader
│   ├── reflector.py      ← L5 self-eval (needs wiring)
│   ├── identity.py       ← L6 identity layer
│   ├── agents.py
│   ├── tools.py
│   ├── planner.py
│   └── executor.py
└── Nova/Nova_Vault_/     ← Obsidian vault
```

---

To resume: Paste this prompt and say _"continuing Project Nova"_ — I'll pick up at reflector integration.# Project Nova — Resume Prompt

Session Handoff | v0.7.0 | Phase 7

---

## System State

- Machine: Windows 11, Legion 7i Pro, RTX 5090 24GB VRAM, 32GB RAM
- RAM Upgrade: 64GB incoming (ETA 1-2 days) — enables full Nemotron 70B
- Current Model: Llama-3.1-8B via LM Studio
- Workspace: `C:/Users/dazch/nova/`
- Vault: Obsidian at `C:/Users/dazch/nova/vault/`
- Repo: `github.com/dazchi312-del/Nova.git` — branch `main`, last commit `b270e2d`

---

## What Was Completed This Session

- `loop.py` fully refactored — all hardcoded constants replaced with dynamic values from `core.config`
- System prompt restructured into two-message format (Identity + Tool Schema)
- `nova_config.json` is BOM-safe and config-driven
- `core/reflector.py` exists and is committed
- `core/identity.py` created and committed
- Vault files committed
- `.gitignore` cleaned up — excludes `__pycache__`, `db/nova.db`, diagnostics, obsidian local config
- Clean push to GitHub — 31 files, commit `b270e2d`

---

## Next Steps (In Order)

1. Wire reflector into `run_loop` in `loop.py`
2. Add reflector config block to `nova_config.json`:
    
    json
    
    ```
    "reflector": {
      "enabled": true,
      "threshold": 0.75,
      "max_revisions": 2
    }
    ```
    
3. Test live self-correction cycle — score a response, trigger revision if below threshold
4. Install 64GB RAM → swap model to Nemotron 70B in LM Studio
5. Resume full Phase 7 development

---

## Architecture Layers (Reference)

|Level|Name|Status|
|---|---|---|
|L1|Perception|✅ Active|
|L2|Memory|✅ Active|
|L3|Planning|✅ Active|
|L4|Execution|✅ Active|
|L5|Self-Evaluation (Reflector)|🔧 Built, needs wiring|
|L6|Identity|✅ Committed|

---

## Key Files

```
C:/Users/dazch/nova/
├── loop.py               ← main run loop (config-driven)
├── nova_config.json      ← master config (BOM-safe)
├── core/
│   ├── config.py         ← config loader
│   ├── reflector.py      ← L5 self-eval (needs wiring)
│   ├── identity.py       ← L6 identity layer
│   ├── agents.py
│   ├── tools.py
│   ├── planner.py
│   └── executor.py
└── Nova/Nova_Vault_/     ← Obsidian vault
```

---

To resume: Paste this prompt and say _"continuing Project Nova"_ — I'll pick up at reflector integration.

