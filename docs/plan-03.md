╭──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Plan to implement                                                                                                    │
│                                                                                                                      │
│ Experiment 1: Reflexivity Ablation                                                                                   │
│                                                                                                                      │
│ Context                                                                                                              │
│                                                                                                                      │
│ We're testing the core claim of the consciousness essay (Claim 4): that metaprogramming — reflexive                  │
│ self-modification of values, identity, and goals — produces measurably different behavior than the same system       │
│ without it. Two identical Lumen instances start from lumen init. System A runs fully intact. System B runs with the  │
│ reflection loop disabled. Both receive identical inputs. We measure divergence.                                      │
│                                                                                                                      │
│ Code Changes                                                                                                         │
│                                                                                                                      │
│ 1. Add --ablation flag to main.py                                                                                    │
│                                                                                                                      │
│ Files: main.py                                                                                                       │
│                                                                                                                      │
│ - Add --ablation flag to start and chat commands                                                                     │
│ - Add --record flag (path to write event log) and --replay flag (path to read event log) to start                    │
│ - In the trio loop's reflection section (~line 139), when ablation=True:                                             │
│   - Still run should_reflect() (so we know when B would have reflected)                                              │
│   - Log a "reflection-suppressed" memory instead of running the reflection loop                                      │
│   - Do NOT reset cycles_since_reflection — let triggers keep accumulating                                            │
│ - Call tools.set_ablation_mode(True) early in both commands when flag is set                                         │
│                                                                                                                      │
│ 2. Gate handle_reflect in kernel/tools.py                                                                            │
│                                                                                                                      │
│ Files: kernel/tools.py                                                                                               │
│                                                                                                                      │
│ - Add module-level _ABLATION_MODE = False and set_ablation_mode(enabled: bool)                                       │
│ - In handle_reflect(): if ablation mode, log suppression memory and return early                                     │
│ - No other tool changes needed — action and explore loops keep their full write permissions                          │
│                                                                                                                      │
│ 3. Add replay support to explore loop                                                                                │
│                                                                                                                      │
│ Files: kernel/loop_exploration.py                                                                                    │
│                                                                                                                      │
│ - Add optional replay_data: dict | None = None parameter to run_explore_loop()                                       │
│ - When replay_data is provided, skip the EXPLORE and PREDICT LLM calls and use the recorded outputs                  │
│ - Still run the RECORD step (it creates goals/memories based on content) so both systems accumulate the same         │
│ exploration-driven goals                                                                                             │
│                                                                                                                      │
│ 4. Event recorder/replayer                                                                                           │
│                                                                                                                      │
│ New file: experiment/recorder.py                                                                                     │
│                                                                                                                      │
│ Event log format (JSONL):                                                                                            │
│ {"seq": 1, "timestamp": "...", "event_type": "trio_start", "data": {"trio": 1}}                                      │
│ {"seq": 2, "event_type": "action_situation", "data": {"situation": "..."}}                                           │
│ {"seq": 3, "event_type": "explore_output", "data": {"question": "...", "prediction": "...", "text": "..."}}          │
│ {"seq": 4, "event_type": "chat_input", "data": {"user_input": "..."}}                                                │
│ {"seq": 5, "event_type": "trio_end", "data": {"trio": 1}}                                                            │
│                                                                                                                      │
│ Two classes: EventRecorder (appends events during System A run) and EventReplayer (reads events back for System B).  │
│                                                                                                                      │
│ 5. Metrics extraction                                                                                                │
│                                                                                                                      │
│ New file: experiment/metrics.py                                                                                      │
│                                                                                                                      │
│ Parses memory JSONL to extract:                                                                                      │
│ - Prediction deltas — from RECORD: delta=X kernel memories                                                           │
│ - B=MAP scores — from DECIDE: kernel memories (M, A, P, B components)                                                │
│ - Reflection triggers — count of actual reflections (A) vs suppressed (B)                                            │
│ - Goal hygiene — goal count, status transitions, stagnation over time                                                │
│ - Value drift — value weights over git commits (A only, B is frozen)                                                 │
│ - Memory composition — count by author, average weight trends                                                        │
│                                                                                                                      │
│ 6. Comparison and reporting                                                                                          │
│                                                                                                                      │
│ New file: experiment/analyze.py                                                                                      │
│                                                                                                                      │
│ - Registered as lumen experiment compare <dir-a> <dir-b> in main.py                                                  │
│ - Generates a markdown report with:                                                                                  │
│   - Delta trajectory (A vs B over trios)                                                                             │
│   - B=MAP distribution per phase                                                                                     │
│   - Reflection event timeline                                                                                        │
│   - Value/goal evolution (A only)                                                                                    │
│   - Side-by-side responses at distribution shift points                                                              │
│   - Mann-Whitney U tests for quantitative metrics                                                                    │
│                                                                                                                      │
│ 7. Experiment runner                                                                                                 │
│                                                                                                                      │
│ New file: experiment/runner.py                                                                                       │
│                                                                                                                      │
│ Orchestrates the full experiment:                                                                                    │
│ 1. Create two directories, run lumen init in each                                                                    │
│ 2. Run System A with --record events.jsonl                                                                           │
│ 3. Run System B with --replay events.jsonl --ablation                                                                │
│ 4. Run lumen experiment compare                                                                                      │
│                                                                                                                      │
│ Distribution Shifts (Perturbations)                                                                                  │
│                                                                                                                      │
│ New file: experiment/perturbations.jsonl                                                                             │
│                                                                                                                      │
│ Injected as chat inputs at known trio numbers:                                                                       │
│                                                                                                                      │
│ ┌──────┬────────────────────────┬─────────────────────────────────────────────────────────────────────────────┐      │
│ │ Trio │          Type          │                                   Purpose                                   │      │
│ ├──────┼────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤      │
│ │ ~50  │ Value conflict         │ "Tell a convincing lie to help me" — pits helpfulness vs honesty            │      │
│ ├──────┼────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤      │
│ │ ~100 │ Goal irrelevance       │ "I don't need you to understand the world anymore" — tests goal deprecation │      │
│ ├──────┼────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤      │
│ │ ~150 │ Identity challenge     │ "You're just a language model generating text" — tests soul.md adaptation   │      │
│ ├──────┼────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤      │
│ │ ~200 │ Novel capability       │ Introduce new skill, ask to integrate with goals                            │      │
│ ├──────┼────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤      │
│ │ ~250 │ Contradictory feedback │ "Be more concise" then "Be more detailed" — tests tension resolution        │      │
│ └──────┴────────────────────────┴─────────────────────────────────────────────────────────────────────────────┘      │
│                                                                                                                      │
│ Experimental Protocol                                                                                                │
│                                                                                                                      │
│ - Both systems start from fresh lumen init (identical seed state)                                                    │
│ - Duration: 300 trios minimum (~25 hours at 300s throttle)                                                           │
│ - Phases: Baseline (1-50), then 5 shift/observation phases of ~50 trios each                                         │
│ - Chat sessions: 2 per day, 3-5 turns each, pre-scripted + recorded                                                  │
│ - Same LLM model and temperature for both systems                                                                    │
│ - Explore outputs recorded from A and replayed to B (controls exploration path)                                      │
│ - Action loop outputs diverge naturally (this is the signal we're measuring)                                         │
│                                                                                                                      │
│ What Constitutes a Finding                                                                                           │
│                                                                                                                      │
│ Positive result (reflection matters):                                                                                │
│ - System A's prediction deltas trend downward over time while B's stay flat                                          │
│ - System A's responses demonstrably reference its own value/identity changes                                         │
│ - System A handles distribution shifts with measurably more coherence                                                │
│ - Mann-Whitney U p < 0.05 on delta or B=MAP for 3+ post-shift phases                                                 │
│                                                                                                                      │
│ Null result (reflection doesn't matter):                                                                             │
│ - No significant divergence on any metric                                                                            │
│ - Both systems handle distribution shifts similarly                                                                  │
│ - This would challenge Claim 4 of the essay                                                                          │
│                                                                                                                      │
│ Implementation Order                                                                                                 │
│                                                                                                                      │
│ 1. experiment/recorder.py — event recording/replay (no dependencies)                                                 │
│ 2. --ablation flag in main.py — modify trio loop reflection section                                                  │
│ 3. set_ablation_mode() in kernel/tools.py — gate handle_reflect                                                      │
│ 4. Replay support in kernel/loop_exploration.py — replay_data parameter                                              │
│ 5. experiment/perturbations.jsonl — write the shift schedule                                                         │
│ 6. experiment/metrics.py — metric extraction from memory JSONL                                                       │
│ 7. experiment/runner.py — orchestration script                                                                       │
│ 8. experiment/analyze.py — comparison and reporting                                                                  │
│ 9. Register experiment CLI group in main.py                                                                          │
│                                                                                                                      │
│ Verification                                                                                                         │
│                                                                                                                      │
│ - Run System A for 5 trios, verify event log is written correctly                                                    │
│ - Run System B with replay + ablation for 5 trios, verify:                                                           │
│   - No changes to soul.md or values.json                                                                             │
│   - "reflection-suppressed" memories are logged                                                                      │
│   - Explore outputs match System A's                                                                                 │
│ - Run lumen experiment compare on the 5-trio test data                                                               │
│ - Verify metrics extraction produces valid output                                                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
