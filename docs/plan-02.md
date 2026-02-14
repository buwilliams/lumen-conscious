╭─────────────────────────────────────────────────────────────────╮
│ Plan to implement                                               │
│                                                                 │
│ Plan: Native LLM Tool-Use for Lumen                             │
│                                                                 │
│ Context                                                         │
│                                                                 │
│ Lumen's loops use one-shot prompt-and-parse: call_llm() -> str  │
│ then extract_json(). The LLM can't invoke anything — it outputs │
│  JSON that the kernel pattern-matches on. Reflection's          │
│ metaprogramming is fragile JSON parsing. The action loop can't  │
│ invoke skills. Chat can't trigger reflection.                   │
│                                                                 │
│ This plan adds native tool-use within each kernel-enforced      │
│ step. The kernel keeps full control of step sequencing          │
│ (THINK→DECIDE→ACT→RECORD, REVIEW→ASK→EVOLVE). The LLM gets      │
│ tools appropriate to each step but cannot skip steps.           │
│                                                                 │
│ Invariants Preserved                                            │
│                                                                 │
│ "The system can change what it thinks/values/is — it cannot     │
│ change how thinking happens."                                   │
│                                                                 │
│ 1. Kernel controls step sequencing — Each step (REVIEW, ASK,    │
│ EVOLVE, etc.) is a separate run_agentic call made by kernel     │
│ Python code. The LLM cannot skip, reorder, or combine steps.    │
│ 2. Write permissions enforced per step —                        │
│ get_tools_for_step(step) only exposes tools permitted for that  │
│ step. REVIEW gets read-only tools. EVOLVE gets write tools. The │
│  LLM can't write values from a THINK step.                      │
│ 3. Kernel memory audit trail is immutable — The kernel writes   │
│ its own memories after each step. The record_memory tool writes │
│  author="self". No tool exists to write or modify kernel        │
│ memories.                                                       │
│ 4. Reflection reads only non-kernel memories — Read tools in    │
│ reflection steps use retrieve_non_kernel_memories().            │
│ 5. No auto-commit — Git commits are a manual user process, not  │
│ kernel behavior.                                                │
│                                                                 │
│ Phase 1: Infrastructure                                         │
│                                                                 │
│ 1.1 Add types to kernel/llm/base.py                             │
│                                                                 │
│ Add dataclasses:                                                │
│ - ToolUseRequest(id, name, arguments)                           │
│ - LLMResponse(text, tool_calls, stop_reason)                    │
│                                                                 │
│ Add complete_with_tools(system, messages, tools, model) ->      │
│ LLMResponse to LLMProvider (default raises                      │
│ NotImplementedError).                                           │
│                                                                 │
│ 1.2 Implement complete_with_tools in kernel/llm/anthropic.py    │
│                                                                 │
│ Use the Anthropic Messages API's native tools parameter. Parse  │
│ response content blocks — text → LLMResponse.text, tool_use →   │
│ LLMResponse.tool_calls.                                         │
│                                                                 │
│ 1.3 Add run_agentic to kernel/llm/__init__.py                   │
│                                                                 │
│ run_agentic(system, user, tools, max_iterations=10) ->          │
│ AgenticResult                                                   │
│                                                                 │
│ Loop: send messages with tool defs → if LLM returns tool_calls, │
│  execute each, append results → repeat until stop_reason ==     │
│ "end_turn" or max iterations. Catch tool execution errors and   │
│ return error strings to the LLM.                                │
│                                                                 │
│ AgenticResult(text, tool_calls_made, iterations) — text is the  │
│ final response, tool_calls_made is the audit trail.             │
│                                                                 │
│ 1.4 Tool registry in config + kernel/tools.py                   │
│                                                                 │
│ Config (config.default.json) — human-readable, declares tool    │
│ names, step permissions, and required tools:                    │
│                                                                 │
│ {                                                               │
│   "tools": {                                                    │
│     "steps": {                                                  │
│       "think": {                                                │
│         "tools": ["read_soul", "read_values", "read_goals",     │
│ "read_memories", "list_skills"],                                │
│         "required": ["read_soul", "read_values", "read_goals",  │
│ "read_memories"]                                                │
│       },                                                        │
│       "decide": {                                               │
│         "tools": ["read_values", "read_goals", "list_skills"],  │
│         "required": ["list_skills"]                             │
│       },                                                        │
│       "act": {                                                  │
│         "tools": ["update_goal_status", "invoke_skill",         │
│ "create_skill", "record_memory"],                               │
│         "required": []                                          │
│       },                                                        │
│       "record": {                                               │
│         "tools": [],                                            │
│         "required": []                                          │
│       },                                                        │
│       "review": {                                               │
│         "tools": ["read_soul", "read_values", "read_goals",     │
│ "read_memories", "list_skills"],                                │
│         "required": ["read_soul", "read_memories",              │
│ "read_values", "read_goals"]                                    │
│       },                                                        │
│       "ask": {                                                  │
│         "tools": ["read_soul", "read_values", "read_goals",     │
│ "read_memories"],                                               │
│         "required": []                                          │
│       },                                                        │
│       "evolve": {                                               │
│         "tools": ["write_soul", "update_value", "update_goal",  │
│ "record_memory"],                                               │
│         "required": ["record_memory"]                           │
│       },                                                        │
│       "explore": {                                              │
│         "tools": ["read_soul", "read_values", "read_goals",     │
│ "read_memories", "record_memory"],                              │
│         "required": ["read_memories", "record_memory"]          │
│       },                                                        │
│       "chat": {                                                 │
│         "tools": ["read_soul", "read_values", "read_goals",     │
│ "read_memories", "list_skills",                                 │
│                   "update_goal_status", "invoke_skill",         │
│ "create_skill", "record_memory", "reflect"],                    │
│         "required": ["read_memories"]                           │
│       }                                                         │
│     }                                                           │
│   }                                                             │
│ }                                                               │
│                                                                 │
│ Kernel validation + retry: After run_agentic returns, the       │
│ kernel checks result.tool_calls_made against the step's         │
│ required list. If any required tool was not called, the kernel  │
│ re-runs the step once with an additional prompt: "You must use  │
│ the following tools: [missing tools]. Please try again." If it  │
│ fails a second time, the kernel logs a warning and continues.   │
│                                                                 │
│ kernel/tools.py — all tool metadata (descriptions, parameter    │
│ schemas, handlers) lives here in Python:                        │
│                                                                 │
│ - TOOL_REGISTRY: dict[str, Tool] — maps tool name → Tool(name,  │
│ description, parameters, handler)                               │
│ - load_tools(step: str) -> list[Tool] — reads                   │
│ config.tools.steps[step], looks up each name in the registry,   │
│ returns the list                                                │
│ - Tool dataclass with schema() (Anthropic format) and           │
│ execute(arguments) methods                                      │
│ - Handler wrappers: handle_update_value, handle_update_goal,    │
│ handle_record_memory, handle_reflect                            │
│                                                                 │
│ Tools defined in the registry:                                  │
│ - Read: read_soul, read_values, read_goals, read_memories,      │
│ list_skills                                                     │
│ - Reflection write: write_soul, update_value, update_goal       │
│ - Action write: update_goal_status, invoke_skill, create_skill  │
│ - Memory: record_memory                                         │
│ - Meta: reflect (chat only — triggers reflection loop)          │
│                                                                 │
│ Phase 2: Convert Reflection Loop                                │
│                                                                 │
│ 2.1 Update prompts for review/, ask/, evolve/                   │
│                                                                 │
│ Update existing system.md files to reference available tools    │
│ instead of asking for JSON output. The LLM should use read      │
│ tools to examine state rather than receiving it pre-formatted   │
│ in the prompt.                                                  │
│                                                                 │
│ Update prompt.md templates: remove pre-loaded state variables   │
│ (soul, values, goals, memories) since the LLM will read these   │
│ via tools. Keep trigger info and review results that flow       │
│ between steps.                                                  │
│                                                                 │
│ 2.2 Convert kernel/reflection.py                                │
│                                                                 │
│ Each step becomes a run_agentic call:                           │
│                                                                 │
│ REVIEW: System prompt instructs LLM to use read tools to        │
│ examine memories, values, goals, soul. LLM produces a text      │
│ summary (patterns, tensions, surprises). Kernel logs a kernel   │
│ memory.                                                         │
│                                                                 │
│ ASK: System prompt + REVIEW text as context. LLM reasons about  │
│ tensions, uses read tools if needed. Produces proposals as      │
│ text. Kernel logs a kernel memory.                              │
│                                                                 │
│ EVOLVE: System prompt + proposals as context. LLM gets write    │
│ tools (update_value, update_goal, write_soul, record_memory).   │
│ LLM calls tools to apply changes. Kernel logs changes.          │
│                                                                 │
│ Delete _apply_changes() and extract_json usage from             │
│ reflection.py.                                                  │
│                                                                 │
│ REVIEW result → ASK input → EVOLVE input: The kernel passes     │
│ each step's AgenticResult.text as context to the next step's    │
│ user prompt. This is how the kernel shuttles information        │
│ between steps without the LLM controlling flow.                 │
│                                                                 │
│ Phase 3: Convert Action Loop                                    │
│                                                                 │
│ 3.1 Update prompts for think/, decide/                          │
│                                                                 │
│ Update to reference tools. THINK uses read tools to examine     │
│ state. DECIDE receives candidates from THINK and reasons        │
│ through B=MAP scoring.                                          │
│                                                                 │
│ 3.2 Create kernel/prompts/act/system.md + prompt.md             │
│                                                                 │
│ New prompt for the ACT step (replaces the current inline skill  │
│ dispatch). Instructs LLM to execute the decided action using    │
│ tools (invoke_skill, create_skill, update_goal_status). For     │
│ respond actions, the LLM's text output is the response.         │
│                                                                 │
│ 3.3 Convert kernel/loops.py                                     │
│                                                                 │
│ Each step becomes a run_agentic call:                           │
│                                                                 │
│ THINK: Read tools. LLM analyzes situation, generates            │
│ candidates. Returns text with analysis.                         │
│                                                                 │
│ DECIDE: Read tools + list_skills. LLM receives THINK output,    │
│ scores with B=MAP, selects action. Returns text with selected   │
│ action.                                                         │
│                                                                 │
│ ACT: Action write tools + record_memory. LLM receives DECIDE    │
│ output, executes the selected action via tools. Returns         │
│ response text.                                                  │
│                                                                 │
│ RECORD: No LLM tools — this step stays as a one-shot call_llm.  │
│ Per spec, RECORD writes kernel-authored memories (the audit     │
│ trail: prediction vs outcome, delta). The kernel writes these   │
│ directly, not via LLM tool call.                                │
│                                                                 │
│ Delete extract_json usage, old JSON parsing, and manual skill   │
│ dispatch from loops.py.                                         │
│                                                                 │
│ should_reflect stays as a one-shot call_llm call — it's a       │
│ kernel gate, not an LLM action.                                 │
│                                                                 │
│ Phase 4: Chat-Triggered Reflection                              │
│                                                                 │
│ 4.1 Create kernel/prompts/chat/system.md + prompt.md            │
│                                                                 │
│ Chat-specific system prompt. Tells LLM it has access to action  │
│ tools and a reflect meta-tool for when the user guides          │
│ self-examination.                                               │
│                                                                 │
│ 4.2 Add reflect meta-tool to kernel/tools.py                    │
│                                                                 │
│ Available only in chat step. Calls                              │
│ run_reflection_loop(triggers) and returns a summary of changes  │
│ made.                                                           │
│                                                                 │
│ 4.3 Convert kernel/chat.py                                      │
│                                                                 │
│ ChatSession.turn uses run_agentic with chat tools. The LLM can  │
│ respond directly (text output), use action tools, or trigger    │
│ reflection. Replaces the current run_action_loop call.          │
│                                                                 │
│ Cleanup                                                         │
│                                                                 │
│ Delete:                                                         │
│ - extract_json from kernel/llm/__init__.py                      │
│ - _apply_changes from kernel/reflection.py                      │
│ - Old JSON parsing patterns throughout loops.py and             │
│ reflection.py                                                   │
│                                                                 │
│ Keep:                                                           │
│ - call_llm as utility for should_reflect and explore (simple    │
│ one-shot, no tools needed)                                      │
│ - All existing prompt template directories (updated in place,   │
│ not replaced)                                                   │
│                                                                 │
│ Files Changed                                                   │
│                                                                 │
│ File: kernel/llm/base.py                                        │
│ Change: Add ToolUseRequest, LLMResponse, complete_with_tools    │
│ ────────────────────────────────────────                        │
│ File: kernel/llm/anthropic.py                                   │
│ Change: Implement complete_with_tools                           │
│ ────────────────────────────────────────                        │
│ File: kernel/llm/__init__.py                                    │
│ Change: Add run_agentic, delete extract_json                    │
│ ────────────────────────────────────────                        │
│ File: config.default.json                                       │
│ Change: Add tools section (definitions + step mapping)          │
│ ────────────────────────────────────────                        │
│ File: kernel/tools.py                                           │
│ Change: New — Tool class, load_tools(step), handler wrappers    │
│ ────────────────────────────────────────                        │
│ File: kernel/prompts/review/system.md                           │
│ Change: Update for tool-use                                     │
│ ────────────────────────────────────────                        │
│ File: kernel/prompts/review/prompt.md                           │
│ Change: Remove pre-loaded state vars                            │
│ ────────────────────────────────────────                        │
│ File: kernel/prompts/ask/system.md                              │
│ Change: Update for tool-use                                     │
│ ────────────────────────────────────────                        │
│ File: kernel/prompts/ask/prompt.md                              │
│ Change: Update — receives review text                           │
│ ────────────────────────────────────────                        │
│ File: kernel/prompts/evolve/system.md                           │
│ Change: Update for tool-use (write tools)                       │
│ ────────────────────────────────────────                        │
│ File: kernel/prompts/evolve/prompt.md                           │
│ Change: Update — receives proposals                             │
│ ────────────────────────────────────────                        │
│ File: kernel/prompts/think/system.md                            │
│ Change: Update for tool-use (read tools)                        │
│ ────────────────────────────────────────                        │
│ File: kernel/prompts/think/prompt.md                            │
│ Change: Remove pre-loaded state vars                            │
│ ────────────────────────────────────────                        │
│ File: kernel/prompts/decide/system.md                           │
│ Change: Update for tool-use                                     │
│ ────────────────────────────────────────                        │
│ File: kernel/prompts/decide/prompt.md                           │
│ Change: Update — receives think output                          │
│ ────────────────────────────────────────                        │
│ File: kernel/prompts/act/                                       │
│ Change: New — ACT step prompts                                  │
│ ────────────────────────────────────────                        │
│ File: kernel/prompts/chat/                                      │
│ Change: New — chat prompts                                      │
│ ────────────────────────────────────────                        │
│ File: kernel/reflection.py                                      │
│ Change: Use run_agentic per step, delete _apply_changes         │
│ ────────────────────────────────────────                        │
│ File: kernel/loops.py                                           │
│ Change: Use run_agentic per step, delete JSON parsing           │
│ ────────────────────────────────────────                        │
│ File: kernel/chat.py                                            │
│ Change: Use run_agentic with reflect meta-tool                  │
│ ────────────────────────────────────────                        │
│ File: docs/spec.md                                              │
│ Change: Remove auto-commit references                           │
│ ────────────────────────────────────────                        │
│ File: CLAUDE.md                                                 │
│ Change: Remove auto-commit reference from reflection loop       │
│   description                                                   │
│                                                                 │
│ Verification                                                    │
│                                                                 │
│ 1. uv run lumen reflect — kernel logs show each step running    │
│ with tool calls; values/goals/soul modified via tools           │
│ 2. uv run lumen run — action loop steps run sequentially,       │
│ skills invoked via tools                                        │
│ 3. uv run lumen chat — conversation works; "reconsider your     │
│ values" triggers reflection                                     │
│ 4. data/memory/ — kernel memories for each step, self memories  │
│ from tool calls                                                 │
│ 5. Update docs/spec.md (lines 272-275) and CLAUDE.md (line 50)  │
│ — remove auto-commit references; git commits are manual         │
╰─────────────────────────────────────────────────────────────────╯
