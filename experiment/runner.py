"""Shared experiment utilities.

Provides _init_system() and _run_system() helpers used by experiment modules.
"""

import time
from pathlib import Path

import click


def _init_system(data_dir: Path):
    """Initialize a Lumen instance with a custom data directory."""
    from kernel.data import set_data_dir
    set_data_dir(data_dir)

    from kernel.init import scaffold
    scaffold()


def _run_system(
    data_dir: Path,
    trios: int,
    throttle: int,
    ablation: bool = False,
    record_path: str | None = None,
    replay_path: str | None = None,
):
    """Run the trio loop for a system with a custom data directory."""
    from kernel.data import set_data_dir
    set_data_dir(data_dir)

    from kernel.loop_action import run_action_loop
    from kernel.loop_exploration import run_explore_loop
    from kernel.loop_reflection import should_reflect, run_reflection_loop
    from kernel import data

    if ablation:
        from kernel.tools import set_ablation_mode
        set_ablation_mode(True)

    recorder = None
    replayer = None
    if record_path:
        from experiment.recorder import EventRecorder
        recorder = EventRecorder(record_path)
    if replay_path:
        from experiment.recorder import EventReplayer
        replayer = EventReplayer(replay_path)

    max_trios = replayer.total_trios if replayer else trios
    effective_trios = min(trios, max_trios)

    label = "A (intact)" if not ablation else "B (ablated)"
    cycles_since_reflection = 0
    recent_prediction_errors = []

    for trio in range(1, effective_trios + 1):
        if recorder:
            recorder.trio_start(trio)

        # --- Action ---
        click.echo(f"  [{label}] trio {trio}: action...", nl=False)
        result = run_action_loop()
        pe = result.get("prediction_error", 0.0)
        recent_prediction_errors.append(pe)
        if len(recent_prediction_errors) > 10:
            recent_prediction_errors = recent_prediction_errors[-10:]
        cycles_since_reflection += 1
        click.echo(f" pe={pe:+.2f}", nl=False)

        # --- Explore ---
        replay_data = None
        if replayer:
            replay_data = replayer.next("explore_output")

        result = run_explore_loop(replay_data=replay_data)
        click.echo(f" explore=ok", nl=False)

        if recorder:
            recorder.explore_output(
                question=result.get("question", ""),
                prediction=result.get("prediction", ""),
                text=result.get("text", ""),
            )

        cycles_since_reflection += 1

        # --- Reflect ---
        trigger = should_reflect(cycles_since_reflection, recent_prediction_errors)
        if trigger.get("should_reflect"):
            if ablation:
                data.append_memory(data.make_memory(
                    author="kernel",
                    weight=0.3,
                    situation="reflection-suppressed",
                    description=f"REFLECT: suppressed by ablation (triggers: {trigger.get('triggers', [])})",
                ))
                click.echo(f" reflect=SUPPRESSED")
            else:
                ref_result = run_reflection_loop(trigger.get("triggers", []))
                changes = ref_result.get("changes", [])
                click.echo(f" reflect={len(changes)} changes")
                cycles_since_reflection = 0
                recent_prediction_errors = []
        else:
            click.echo(f" reflect=skip")

        if recorder:
            recorder.trio_end(trio)

        if trio < effective_trios and throttle > 0:
            time.sleep(throttle)

    # Reset ablation mode after run
    if ablation:
        from kernel.tools import set_ablation_mode
        set_ablation_mode(False)
