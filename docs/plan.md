╭─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Plan to implement                                                                                                   │
│                                                                                                                     │
│ Lumen Phase 1 Implementation Plan                                                                                   │
│                                                                                                                     │
│ Context                                                                                                             │
│                                                                                                                     │
│ The Lumen project has a complete architecture spec (docs/spec.md) but zero code. Phase 1's goal per the spec:       │
│ "Build the three loops (action, explore, reflection), the data layer, the chat skill, and the CLI. Run it. Watch    │
│ it." This plan implements the full Phase 1 system incrementally, where each step produces something testable.       │
│                                                                                                                     │
│ ---                                                                                                                 │
│ Decisions                                                                                                           │
│                                                                                                                     │
│ - LLM: Provider-agnostic abstraction (kernel/llm/) supporting Anthropic (Claude), OpenAI (ChatGPT), and xAI (Grok). │
│  Active provider and model set in config. All kernel code calls the abstraction, never a provider SDK directly.     │
│ - CLI: click for command parsing.                                                                                   │
│ - Config: config.default.json (committed) holds defaults. config.json (gitignored) holds user overrides. Merged at  │
│ load time — overrides win. Contains model name, API key env var names, thresholds, cycle settings, etc.             │
│ - Structured output: LLM returns JSON blocks in markdown fences. A utility function in the LLM abstraction extracts │
│  and parses them. Each provider's complete() method returns raw text; parsing is provider-agnostic.                 │
│ - Prompt templates: {{variable}} syntax with simple string replacement. No templating library.                      │
│ - Memory retrieval: Start with recency-only. Add semantic (embedding) retrieval as a fast-follow once loops work.   │
│ - Chat: Lives in the kernel (no chat skill). kernel/chat.py is a thin REPL that feeds user input through the        │
│ kernel's actual loops. User input becomes an external memory and a trigger for the action loop — the consciousness  │
│ emerges from the loop process (THINK → DECIDE → ACT → RECORD), not from prompt engineering. Conversation history    │
│ maintained for continuity across turns.                                                                             │
│                                                                                                                     │
│ ---                                                                                                                 │
│ Build Order                                                                                                         │
│                                                                                                                     │
│ Step 1: Project scaffolding                                                                                         │
│                                                                                                                     │
│ Create pyproject.toml, config files, and stub main.py.                                                              │
│                                                                                                                     │
│ File: pyproject.toml                                                                                                │
│ Purpose: name=lumen, deps: anthropic, openai, xai-sdk, click. Entry: lumen = "main:cli"                             │
│ ────────────────────────────────────────                                                                            │
│ File: config.default.json                                                                                           │
│ Purpose: Committed defaults: model, embedding_model, reflection_cycle_interval, motivation_threshold,               │
│   memory_retrieve_count, etc.                                                                                       │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/config.py                                                                                              │
│ Purpose: load_config() — reads config.default.json, deep-merges config.json overrides if it exists. Returns dict.   │
│ ────────────────────────────────────────                                                                            │
│ File: main.py                                                                                                       │
│ Purpose: click.group() with stub subcommands: init, chat, run, reflect, status, memory, values, goals, skills       │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/__init__.py                                                                                            │
│ Purpose: Package marker                                                                                             │
│                                                                                                                     │
│ Add config.json to .gitignore.                                                                                      │
│                                                                                                                     │
│ Test: uv run lumen --help prints all commands.                                                                      │
│                                                                                                                     │
│ Step 2: Data layer                                                                                                  │
│                                                                                                                     │
│ All file I/O for data/ in one module. Every other module depends on this.                                           │
│                                                                                                                     │
│ File: kernel/data.py                                                                                                │
│ Purpose: Read/write functions for soul.md, values.json, goals/[year].json, memory JSONL. Skill listing. Type        │
│   definitions (dataclasses).                                                                                        │
│                                                                                                                     │
│ Key functions:                                                                                                      │
│ - read_soul(), write_soul()                                                                                         │
│ - read_values(), write_values()                                                                                     │
│ - read_goals(), write_goals(), read_active_goals(), read_perpetual_goals(), update_goal_status()                    │
│ - append_memory(), read_memories(), read_recent_memories()                                                          │
│ - list_skills(), get_skill_help()                                                                                   │
│ - create_conversation(), append_turn(), read_conversation() — manage conversation sessions in                       │
│ data/conversations/[session_id].jsonl                                                                               │
│                                                                                                                     │
│ Test: Round-trip writes and reads on each data type.                                                                │
│                                                                                                                     │
│ Step 3: Init command                                                                                                │
│                                                                                                                     │
│ Scaffold a new instance with seed data.                                                                             │
│                                                                                                                     │
│ File: kernel/init.py                                                                                                │
│ Purpose: scaffold(): creates data/, soul.md, values.json (honesty/curiosity/helpfulness), goals/2026.json           │
│ (perpetual                                                                                                          │
│   goals), memory/, conversations/, skills/                                                                          │
│                                                                                                                     │
│ Seeds:                                                                                                              │
│ - Values: honesty(0.8), curiosity(0.8), helpfulness(0.7) — all active                                               │
│ - Goals: understand the world(0.9, perpetual), be helpful to the user(0.8, perpetual)                               │
│ - Soul: minimal identity template                                                                                   │
│                                                                                                                     │
│ Wire init command in main.py.                                                                                       │
│                                                                                                                     │
│ Test: uv run lumen init creates valid directory tree with valid JSON files.                                         │
│                                                                                                                     │
│ Step 4: Chat module (kernel)                                                                                        │
│                                                                                                                     │
│ Chat is a thin REPL layer that feeds user input through the kernel's loops. The consciousness emerges from the loop │
│  process, not from prompt construction.                                                                             │
│                                                                                                                     │
│ File: kernel/chat.py                                                                                                │
│ Purpose: ChatSession class: manages conversation turns, stores sessions in data/conversations/[session_id].jsonl.   │
│   Methods: start(), turn(user_input) -> response, load(session_id). Each turn: record user input as external memory │
│  →                                                                                                                  │
│   pass it as the situation to the action loop → the action loop runs its full cycle (THINK → DECIDE → ACT → RECORD) │
│  →                                                                                                                  │
│   return whatever the loop produces. Conversation history kept for turn continuity.                                 │
│                                                                                                                     │
│ The key principle: user input doesn't bypass the loops. It enters the system the same way any external stimulus     │
│ does — as a trigger that the kernel processes through its full decision-making machinery. The response is the       │
│ output of that process.                                                                                             │
│                                                                                                                     │
│ Test: Create a ChatSession, call turn("hello"), verify action loop ran (memories written) and a response was        │
│ returned.                                                                                                           │
│                                                                                                                     │
│ Step 5: LLM abstraction                                                                                             │
│                                                                                                                     │
│ A provider-agnostic layer. All kernel code calls kernel.llm, never a provider SDK directly.                         │
│                                                                                                                     │
│ File: kernel/llm/__init__.py                                                                                        │
│ Purpose: Exports call_llm(system, user) and get_embeddings(texts). Reads provider/model from config, delegates to   │
│ the                                                                                                                 │
│   active provider module.                                                                                           │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/llm/base.py                                                                                            │
│ Purpose: LLMProvider protocol/ABC: complete(system, user, tools?) -> str, embed(texts) -> list[list[float]]. Common │
│                                                                                                                     │
│   interface all providers implement.                                                                                │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/llm/anthropic.py                                                                                       │
│ Purpose: Anthropic provider — uses anthropic SDK. Implements complete() and embed() (embed raises                   │
│ NotImplementedError,                                                                                                │
│   use OpenAI for embeddings).                                                                                       │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/llm/openai.py                                                                                          │
│ Purpose: OpenAI provider — uses openai SDK. Implements complete() and embed().                                      │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/llm/xai.py                                                                                             │
│ Purpose: xAI/Grok provider — uses xai-sdk (xAI's own Python SDK). Implements complete() via client.chat.create() +  │
│   chat.sample().                                                                                                    │
│                                                                                                                     │
│ Config selects the active provider and model:                                                                       │
│ {                                                                                                                   │
│   "llm": {                                                                                                          │
│     "provider": "anthropic",                                                                                        │
│     "model": "claude-sonnet-4-20250514"                                                                             │
│   },                                                                                                                │
│   "embedding": {                                                                                                    │
│     "provider": "openai",                                                                                           │
│     "model": "text-embedding-3-small"                                                                               │
│   }                                                                                                                 │
│ }                                                                                                                   │
│                                                                                                                     │
│ Provider and embedding provider can differ (e.g., Claude for reasoning, OpenAI for embeddings).                     │
│                                                                                                                     │
│ Test: call_llm("You are a test.", "Say hello.") returns a string. Swap provider in config, same call works.         │
│                                                                                                                     │
│ Step 6: Prompt templates                                                                                            │
│                                                                                                                     │
│ 18 markdown files — system.md + prompt.md for each of 9 steps.                                                      │
│                                                                                                                     │
│ File: kernel/prompts.py                                                                                             │
│ Purpose: load_prompt(step, variables) -> (system, user) — loads and renders templates                               │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/prompts/think/{system,prompt}.md                                                                       │
│ Purpose: THINK: analyze situation, generate candidates, predict outcomes                                            │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/prompts/decide/{system,prompt}.md                                                                      │
│ Purpose: DECIDE: score candidates via B=MAP                                                                         │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/prompts/record/{system,prompt}.md                                                                      │
│ Purpose: RECORD: compare prediction vs outcome, compute delta                                                       │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/prompts/explore/{system,prompt}.md                                                                     │
│ Purpose: EXPLORE: generate open-ended question from perpetual goals                                                 │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/prompts/trigger/{system,prompt}.md                                                                     │
│ Purpose: TRIGGER: evaluate whether to enter reflection                                                              │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/prompts/review/{system,prompt}.md                                                                      │
│ Purpose: REVIEW: summarize events since last reflection                                                             │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/prompts/ask/{system,prompt}.md                                                                         │
│ Purpose: ASK: counterfactual reasoning on self, propose changes                                                     │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/prompts/evolve/{system,prompt}.md                                                                      │
│ Purpose: EVOLVE: consistency-check proposals, apply changes                                                         │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/prompts/summarize/{system,prompt}.md                                                                   │
│ Purpose: SUMMARIZE: create yearly memory summary                                                                    │
│                                                                                                                     │
│ Test: load_prompt("think", {...}) returns two non-empty rendered strings.                                           │
│                                                                                                                     │
│ Step 7: Memory retrieval                                                                                            │
│                                                                                                                     │
│ File: kernel/memory.py                                                                                              │
│ Purpose: retrieve_memories(n=20) — recency-based for now. Weight decay function. Semantic retrieval stubbed for     │
│ later.                                                                                                              │
│                                                                                                                     │
│ Test: Append 30 memories, retrieve 20, verify ordering.                                                             │
│                                                                                                                     │
│ Step 8: Skill invocation + Action/Explore loops                                                                     │
│                                                                                                                     │
│ File: kernel/skills.py                                                                                              │
│ Purpose: invoke_skill(name, input) — runs skill as subprocess via uv run --directory skills/[name], JSON            │
│ stdin/stdout.                                                                                                       │
│   create_skill(name, description, code) — built-in skill authoring tool (creates dir with pyproject.toml +          │
│ main.py).                                                                                                           │
│ ────────────────────────────────────────                                                                            │
│ File: kernel/loops.py                                                                                               │
│ Purpose: run_action_loop(situation?) — THINK → DECIDE → ACT → RECORD. run_explore_loop() — generate question,       │
│ record.                                                                                                             │
│                                                                                                                     │
│ Action loop flow:                                                                                                   │
│ 1. THINK: load state → LLM generates candidates with predictions → log kernel memory                                │
│ 2. DECIDE: LLM scores via B=MAP → select highest B → log kernel memory                                              │
│ 3. ACT: invoke skill as subprocess → capture output                                                                 │
│ 4. RECORD: LLM compares prediction vs outcome → log delta as kernel memory                                          │
│                                                                                                                     │
│ Explore loop flow:                                                                                                  │
│ 1. Load soul, values, perpetual goals, recent memories                                                              │
│ 2. LLM generates one open-ended question                                                                            │
│ 3. Record question as self memory, mechanics as kernel memory                                                       │
│                                                                                                                     │
│ Test: run_action_loop("User said hello") — verify memories written, skill invoked.                                  │
│                                                                                                                     │
│ Step 9: Reflection loop                                                                                             │
│                                                                                                                     │
│ File: kernel/reflection.py                                                                                          │
│ Purpose: should_reflect(memories, cycles) — check trigger conditions. run_reflection_loop(triggers?) — REVIEW → ASK │
│  →                                                                                                                  │
│   EVOLVE.                                                                                                           │
│                                                                                                                     │
│ Trigger conditions: prediction delta threshold, value conflict, goal completion/staleness, periodic (every N        │
│ cycles), explicit request.                                                                                          │
│                                                                                                                     │
│ EVOLVE applies changes to values.json, goals, soul.md. Git is handled manually by the user — no auto-commit.        │
│                                                                                                                     │
│ Test: run_reflection_loop(triggers=["periodic"]) — verify state modified.                                           │
│                                                                                                                     │
│ Step 10: Wire CLI commands                                                                                          │
│                                                                                                                     │
│ Update main.py with full implementations:                                                                           │
│ - lumen chat: Creates a ChatSession from kernel/chat.py. REPL loop calling session.turn(input) each iteration.      │
│ Ctrl+C exits gracefully.                                                                                            │
│ - lumen run: continuous loop alternating action/explore, reflection trigger after each action                       │
│ - lumen reflect: direct call to reflection loop                                                                     │
│ - lumen status: print soul summary, values, goals, memory counts                                                    │
│ - lumen memory: filtered memory display (--author, --date, --all)                                                   │
│ - lumen values: sorted value list                                                                                   │
│ - lumen goals: filtered goal list (--year, --status)                                                                │
│ - lumen skills: scan and list skills                                                                                │
│                                                                                                                     │
│ Test: Full end-to-end: uv run lumen init && uv run lumen chat → type message → get response.                        │
│                                                                                                                     │
│ ---                                                                                                                 │
│ File Manifest (37 files)                                                                                            │
│                                                                                                                     │
│ pyproject.toml                                                                                                      │
│ config.default.json                                                                                                 │
│ main.py                                                                                                             │
│ kernel/__init__.py                                                                                                  │
│ kernel/config.py                                                                                                    │
│ kernel/data.py                                                                                                      │
│ kernel/init.py                                                                                                      │
│ kernel/llm/__init__.py                                                                                              │
│ kernel/llm/base.py                                                                                                  │
│ kernel/llm/anthropic.py                                                                                             │
│ kernel/llm/openai.py                                                                                                │
│ kernel/llm/xai.py                                                                                                   │
│ kernel/prompts.py                                                                                                   │
│ kernel/memory.py                                                                                                    │
│ kernel/skills.py                                                                                                    │
│ kernel/loops.py                                                                                                     │
│ kernel/reflection.py                                                                                                │
│ kernel/chat.py                                                                                                      │
│ kernel/prompts/think/system.md                                                                                      │
│ kernel/prompts/think/prompt.md                                                                                      │
│ kernel/prompts/decide/system.md                                                                                     │
│ kernel/prompts/decide/prompt.md                                                                                     │
│ kernel/prompts/record/system.md                                                                                     │
│ kernel/prompts/record/prompt.md                                                                                     │
│ kernel/prompts/explore/system.md                                                                                    │
│ kernel/prompts/explore/prompt.md                                                                                    │
│ kernel/prompts/trigger/system.md                                                                                    │
│ kernel/prompts/trigger/prompt.md                                                                                    │
│ kernel/prompts/review/system.md                                                                                     │
│ kernel/prompts/review/prompt.md                                                                                     │
│ kernel/prompts/ask/system.md                                                                                        │
│ kernel/prompts/ask/prompt.md                                                                                        │
│ kernel/prompts/evolve/system.md                                                                                     │
│ kernel/prompts/evolve/prompt.md                                                                                     │
│ kernel/prompts/summarize/system.md                                                                                  │
│ kernel/prompts/summarize/prompt.md                                                                                  │
│                                                                                                                     │
│ ---                                                                                                                 │
│ Verification                                                                                                        │
│                                                                                                                     │
│ 1. uv run lumen --help — all 9 commands listed                                                                      │
│ 2. uv run lumen init — data/ tree created with valid JSON                                                           │
│ 3. uv run lumen status — shows soul, values, goals, memory count                                                    │
│ 4. uv run lumen chat — type a message, get an LLM-driven response, memory recorded                                  │
│ 5. uv run lumen run — alternates action/explore cycles, triggers reflection when conditions met                     │
│ 6. uv run lumen reflect — modifies values/soul                                                                      │
│ 7. uv run lumen memory — shows recorded memories with author filtering                                              │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
