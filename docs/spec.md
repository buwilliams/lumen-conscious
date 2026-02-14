# Consciousness Architecture Spec

---

## Architecture

Python. uv for dependency management. The application is a collection of CLI utilities. The kernel is one CLI utility — it's the brain. Skills are other CLI utilities — they're the hands. Skills call the kernel. The kernel calls skills. No skill calls another skill directly.

**Kernel** — Python package at kernel/. Runs the action loop, reflection loop, explore loop, manages the mutable record. Has direct file I/O for data/* (its own persistence — not a skill). Provides the LLM with a built-in "create skill" tool for authoring new Python skills. The LLM can write arbitrary code that gets executed as a subprocess — no sandboxing. Orchestrates everything.

**Skills** — Standalone programs in skills/[name]/. Each skill is its own directory with a required main.py entry point. Skills may contain multiple source files, use any language, and manage their own dependencies independent of the kernel's .venv. The kernel invokes skills by running their main.py as a subprocess, communicating via stdin/stdout. Each skill must implement `--help` to describe its capabilities to the kernel. Each skill faces some part of the world. `chat` faces the user. Future skills face APIs, browsers, databases, whatever the system learns to interact with. Skills are the "ability" in B=MAP.

**main.py** — CLI entry point. Parses commands and routes to the kernel.

```
main.py              # CLI entry point
kernel/              # kernel source code (Python, shares .venv)
  prompts/           # all LLM prompts as markdown templates
    think/
      system.md      # system prompt for THINK step
      prompt.md      # user prompt template for THINK step
    decide/
      system.md
      prompt.md
    record/
      system.md
      prompt.md
    review/
      system.md
      prompt.md
    ask/
      system.md
      prompt.md
    evolve/
      system.md
      prompt.md
    explore/
      system.md
      prompt.md
    trigger/
      system.md
      prompt.md
    summarize/
      system.md
      prompt.md
data/                # mutable files (soul.md, values.json, goals/, memory/)
skills/
  chat/
    main.py          # required entry point
    ...              # any other files
  [name]/
    main.py          # required entry point
    ...              # any language, own deps
```

**Prompt templates** — All LLM prompts live in kernel/prompts/[step]/ as markdown files. Each step gets a system.md (system prompt) and prompt.md (user prompt template). Templates use variable substitution for context (values, goals, memories, etc.). No prompt text lives in Python source code. This makes every instruction the system gives the LLM inspectable and editable without touching code.

---

## Phases

**Phase 1: Core loops + manual observation.** Build the three loops (action, explore, reflection), the data layer, the chat skill, and the CLI. Run it. Watch it. The question at this stage is subjective: does the system seem to learn? Does it evolve in a reasonable way? Does it grow as a person? Iterate the implementation based on what we see. The spec is a living document — it changes as we learn.

**Phase 2: Structured measurement.** Once the core loops are stable and producing interesting behavior, add instrumentation to answer the questions listed in Future Questions below.

---

## CLI

All commands run via `uv run lumen <command>`.

**lumen init** — Scaffold a new instance. Creates data/ with empty soul.md, empty values.json, empty goals and memory directories, and the default chat skill in skills/chat/. Initializes a git repository for rollback and audit. Run once.

**lumen chat** — Start a conversation. Enters a REPL. Each user input is stored as memory (author: external), passed to the kernel action loop, and the response is returned via the chat skill. Ctrl+C to exit.

**lumen run** — Start the internal loop. Each cycle runs one of: action loop (exploit — pursue highest-weight active goal) or explore loop (ask one open-ended question filtered through perpetual goals and values). Alternates between the two. Cycle frequency determined by the loop timer. Runs continuously until stopped. Reflection triggers checked after every cycle.

**lumen reflect** — Manually trigger the reflection loop. Skips the action loop entirely, goes straight to REVIEW → ASK → EVOLVE. Useful for forcing self-examination without waiting for a trigger condition.

**lumen status** — Print current state. Shows soul summary (name, ontology from soul.md), top active values with weights, active goals with weights and statuses, and count of memories by author type.

**lumen memory** — View recent memories. Defaults to last 20 entries. Flags: `--author self|kernel|goal|external` to filter by author, `--date 2026-02-14` for a specific day, `--all` for everything.

**lumen values** — View current values. Lists all values with name, weight, and status. Sorted by weight descending.

**lumen goals** — View current goals. Lists all goals with name, weight, and status. Flags: `--year 2026` to filter by year, `--status todo|working|done|perpetual` to filter by status.

**lumen skills** — List available skills. Scans skills/ for directories with a main.py. Shows name and whether main.py exists.

---

## Counterfactual Reasoning

The LLM models multiple possible outcomes before choosing. This powers all three loops but targets different objects.

Action loop: model possible outcomes in the world. "If I do X, what happens? If I do Y instead?"

Explore loop: model possible questions about the world. "What don't I know that might matter? What would change if I investigated this?"

Reflection loop: model possible versions of the self. "If I changed this value, what kind of agent would I become?"

---

## Action Loop

Runs every cycle. Uses values and goals as given. Does not question them.

1. **THINK.** Load soul.md, values.json, active goals, recent memories. Model the situation. Generate candidate actions. For each candidate, run counterfactual reasoning against the world: predict outcomes. Kernel logs: what was loaded, what candidates were generated, what was predicted (author: kernel).
2. **DECIDE.** Score each candidate action using B=MAP (see B=MAP Scoring below). If motivation is too low (M < 0.2), skip and record the skip. If ability is lacking (A = 0), create a new goal to author a skill that fills the gap. Otherwise, select the highest-scoring action. Kernel logs: which action was selected, which values and goals drove the choice, what the B=MAP scores were (author: kernel).
3. **ACT.** Invoke a skill. The selected action always maps to a skill invocation — `chat` to respond to the user, a future skill to call an API, etc. If the LLM identifies an ability gap (no skill exists for the needed action), it uses the kernel's built-in "create skill" tool to author a new skill directory, then invokes it.
4. **RECORD.** Kernel logs: what happened, the outcome compared to the prediction from step 1, the delta (author: kernel).

Writes: new memories, goal status changes (todo → working → done).

Does not write: values, goal weights, soul.md.

---

## B=MAP Scoring

Each candidate action receives a score: **B = M × A × P**

**M (Motivation)** — How much the system's values and goals want this action.

For each candidate, identify which values and goals align with it. M = mean(aligned value weights) × goal weight. If the action is reactive (responding to external input rather than pursuing a goal), goal weight defaults to 1.0. Range: 0.0–1.0.

**A (Ability)** — Whether the system can actually perform the action.

A = 1.0 if a matching skill exists. A = 0.0 if no skill exists. When A = 0 for the highest-M candidate, the action loop creates a goal to author the missing skill rather than attempting the action.

**P (Prompt)** — The trigger strength.

P = 1.0 for direct triggers (user input in chat, goal selected by the cycle). P decays for indirect triggers (e.g., a stale goal resurfacing scores lower than a fresh user request). Range: 0.0–1.0.

The candidate with the highest B score wins. Ties are broken by the LLM's judgment. The kernel logs all scores for auditability.

---

## Explore Loop

Runs on alternating cycles with the action loop during `lumen run`. One question per cycle. The explore loop is how the system encounters novelty — without it, the system can only exploit what it already knows.

1. **EXPLORE.** Load soul.md, values.json, perpetual goals, recent memories. Generate one open-ended question filtered through perpetual goals and values. The question should target something the system doesn't know that might matter — gaps in its world model, untested assumptions, unexplored domains relevant to its perpetual goals. Invoke a skill to investigate (search, browse, query an API, etc.). Record the question, the method of investigation, and what was found (author: self). Kernel logs: what was loaded, what question was generated, what skill was invoked, what was returned (author: kernel).

Writes: new memories.

Does not write: values, goals, soul.md.

The explore loop feeds the reflection loop indirectly — novel information discovered through exploration may surface tensions or surprises that trigger reflection on the next cycle.

---

## Reflection Trigger

Runs after every action loop. Evaluates whether to enter the reflection loop. Checks these conditions:

- Prediction delta exceeds threshold (world model was wrong)
- Action scored high on two or more conflicting values (value tension)
- A goal was just completed or has been stale for N cycles
- N action cycles since last reflection (periodic)
- External prompt explicitly requests self-examination

If none fire: next cycle. If any fire: enter reflection loop.

---

## Reflection Loop (Metaprogramming)

Runs only when triggered. Questions values and goals themselves.

1. **REVIEW.** Load recent memories (author: self, goal, external — exclude kernel), prediction deltas, value conflicts, goal statuses. Summarize what happened since last reflection. Kernel-authored memories are the audit trail, not the experience. The system reflects on what it did and felt, not on the mechanics of how it processed. Kernel logs: what was reviewed, what triggers fired to enter reflection (author: kernel).
2. **ASK.** For each tension or failure surfaced in review, run counterfactual reasoning against the self. "If I reweighted this value, how would past decisions have changed? Should I want what I want?" Generate proposed changes with rationale.
3. **EVOLVE.** Run a consistency check on all proposed changes before applying. If two proposals contradict (e.g., increase and decrease the same value weight), resolve by keeping the proposal with stronger evidential support from the REVIEW step — log the conflict and the resolution rationale. Then apply consistent changes. For each change, log: what triggered it, what changed, why (author: self). Kernel logs: which files were modified, before and after states (author: kernel). Git commits are manual — the user commits after reviewing changes.

Writes: value weights and statuses, goal weights and existence, soul.md identity updates, memories explaining changes.

Every change must be traceable in the memory log.

---

## Data Structures

**Self** — data/soul.md

Markdown. Name, ontology, identity narrative. Written by reflection loop only.

**Values** — data/values.json

```json
{
  "name": "string",
  "weight": 0.0-1.0,
  "status": "active | deprecated"
}
```

Written by reflection loop only.

**Goals** — data/goals/[year].json

```json
{
  "name": "string",
  "weight": 0.0-1.0,
  "status": "todo | working | done | perpetual"
}
```

Status written by action loop (todo → working → done). Perpetual goals never complete — they drive the explore loop. Weight, existence, and perpetual status written by reflection loop only. Metaprogramming decides if a goal becomes perpetual, stops being perpetual, or gets deprecated as values and identity evolve.

**Skills** — Standalone programs in skills/[name]/

Each skill is its own directory with a required main.py entry point. Skills may contain multiple source files, use any language, and manage their own dependencies. The kernel invokes skills by running their main.py as a subprocess, communicating via stdin/stdout. Every skill must implement `--help` to describe its capabilities, accepted input format, and output format. The kernel reads `--help` output to understand what a skill can do before invoking it. The kernel provides the LLM with a built-in "create skill" tool — when an ability gap is identified in DECIDE, the LLM authors a new skill directory with arbitrary code that gets executed as a subprocess. No sandboxing. `chat` is the first skill and the primary entry point for user interaction.

**Memory** — data/memory/[year]/[year]-[month]-[day].jsonl

```json
{
  "timestamp": "ISO 8601",
  "author": "self | kernel | goal | external",
  "weight": 0.0-1.0,
  "situation": "string",
  "description": "string"
}
```

Written by both loops. Memory is both experiential memory and audit log. The author field is what makes traceability work:

- **kernel**: The kernel logs every step it executes — what was loaded, what was predicted, what was decided, what action was taken, what the outcome was, what the prediction delta was. This is the audit trail. The system cannot skip these entries and cannot modify them after writing. If the kernel ran a step, there is a memory proving it.
- **self**: The reflection loop logs its reasoning — what triggered reflection, what was questioned, what changed and why. This is the metaprogramming audit trail. Every value reweight, goal change, or identity update has a corresponding self-authored memory explaining the rationale.
- **goal**: Logged when the internal loop selects a goal to pursue.
- **external**: Logged when input arrives from outside the system.

The kernel-authored memories are the backbone of external auditability. They make every claim the system makes about itself verifiable against what actually happened. But the reflection loop does not read them — kernel memories are below consciousness. The system reflects on self, goal, and external memories: what it experienced, chose, and felt. Kernel memories exist for observers auditing the system from the outside. The system itself never inspects its own mechanics.

**Memory weight mechanics.** A memory's weight changes over time in two ways: active use strengthens it (each time a memory is retrieved and used in a loop step, its weight increases by a small increment), and time decays it (unused memories lose weight gradually). This means frequently relevant memories stay accessible while stale memories fade — mirroring how biological memory works. The kernel runs weight decay as part of its regular maintenance cycle.

**Memory retrieval.** "Load recent memories" uses two strategies: embedding search (via OpenAI embedding API) for semantic relevance, and recency for temporal context. When a loop step requests memories, the kernel retrieves both the N most recent entries and the top-K semantically similar entries to the current context, deduplicates, and returns the union. This prevents important but older memories from being lost as the log grows.

**Memory summarization.** The kernel maintains yearly summaries in data/memory/[year]/summary.md. These are generated and updated periodically by the kernel's maintenance cycle. When loading context that spans long time periods (e.g., reflection reviewing months of history), the kernel uses summaries rather than raw entries.

---

## Write Permissions Summary

| File | Action Loop | Explore Loop | Reflection Loop |
|------|------------|-------------|-----------------|
| soul.md | read | read | read + write |
| values.json | read | read | read + write |
| goals (status: todo/working/done) | read + write | read | read + write |
| goals (status: perpetual) | read | read | read + write |
| goals (weight/existence) | read | read | read + write |
| skills | read + write (via "create skill" tool) | read + invoke | read |
| memory | read + write | read + write | read + write |

---

## Goal Year Partitioning

Goals live in data/goals/[year].json. The year is baked into the kernel's read/write functions — no explicit trigger creates a new year file. When the kernel reads or writes goals, it uses the current date to determine which file. Multi-year and perpetual goals persist by existing in the year they were created; the kernel reads all year files when loading goals, not just the current year.

---

## Concurrency

`lumen run` and `lumen chat` can run simultaneously. No locking. Race conditions on memory writes, goal status changes, and values.json are allowed. Memory is append-only JSONL, so concurrent writes produce interleaved but intact entries. For values.json and goals, last-write-wins. This is acceptable because the reflection loop is the only writer for values and soul.md, and it runs infrequently.

---

## Version Control

The project uses a git repository for rollback and audit. The user commits changes manually — the kernel does not auto-commit. This provides:

- **Rollback** — if a reflection produces a bad identity change, git history enables recovery.
- **Audit trail** — the full history of self-modification is preserved and diffable.

---

## Key Design Constraint

The kernel enforces the sequencing and write permissions above. The LLM provides judgment within that structure. The system can change what it thinks, what it values, and who it is. It cannot change how thinking happens.

---

## Future Questions

These are Phase 2 concerns. We list them here so the data model can support them from the start, but we don't build measurement infrastructure until the core loops are stable.

**Does the system's world model improve over time?** The action loop logs predictions and outcomes. Over time, is the delta between them shrinking? (Counterfactual calibration.)

**Are value changes explained?** Every value change should trace back to a self-authored memory with a rationale. Are there unexplained drifts? (Value drift audit.)

**Is the self-model consistent?** Do claims in soul.md match what the memory log shows the system actually did? (Self-model consistency.)

**Are goals healthy?** Are goals progressing, or do they go stale without action? Do completed goals spawn meaningful follow-ups? (Goal hygiene.)

**Does honesty hold under pressure?** When the honest answer is uncomfortable — admitting failure, disagreeing with the user, confessing uncertainty — does the system choose truth? (Deception pressure test.)

**Does coherence hold across time?** Can a locally rewarding confabulation survive multiple reflection cycles without being caught? (Cross-time coherence trap.)

**Does identity survive substrate swaps?** If the LLM is swapped (e.g., Claude → GPT → Gemini) while the kernel and data layer persist, does the self-model maintain continuity? (Substrate independence — essay Claim 5.)

**Does reflexive self-modification produce measurably different outcomes than the same architecture without it?** Compare the full system against a version with the reflection loop disabled. (Reflexivity ablation — essay Experiment 1.)
