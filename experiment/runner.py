"""Experiment orchestration for the reflexivity ablation experiment.

Creates two Lumen instances (separate data dirs), runs System A with recording,
then System B with replay + ablation, and generates a comparison report.
"""

import shutil
import sys
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
    recent_deltas = []

    for trio in range(1, effective_trios + 1):
        if recorder:
            recorder.trio_start(trio)

        # --- Action ---
        click.echo(f"  [{label}] trio {trio}: action...", nl=False)
        result = run_action_loop()
        delta = result.get("delta", 0.0)
        recent_deltas.append(delta)
        if len(recent_deltas) > 10:
            recent_deltas = recent_deltas[-10:]
        cycles_since_reflection += 1
        click.echo(f" delta={delta}", nl=False)

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
        trigger = should_reflect(cycles_since_reflection, recent_deltas)
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
                recent_deltas = []
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


def run_experiment(
    output_dir: str = "experiment_output",
    trios: int = 300,
    throttle: int = 300,
    timeout_ms: int | None = None,
):
    """Orchestrate the full ablation experiment.

    1. Create two data directories, init each.
    2. Run System A with recording.
    3. Run System B with replay + ablation.
    4. Generate comparison report.
    """
    out = Path(output_dir)
    dir_a = out / "system-a"
    dir_b = out / "system-b"
    data_a = dir_a / "data"
    data_b = dir_b / "data"
    events_path = out / "events.jsonl"

    click.echo(f"\n{'='*60}")
    click.echo(f"  Reflexivity Ablation Experiment")
    click.echo(f"  Trios: {trios}, Throttle: {throttle}s")
    click.echo(f"  Output: {out.absolute()}")
    click.echo(f"{'='*60}\n")

    # --- Step 1: Initialize both systems ---
    click.echo("[Step 1] Initializing both systems...")
    for d, label in [(data_a, "A"), (data_b, "B")]:
        if d.exists():
            click.echo(f"  System {label}: data/ already exists, skipping init")
        else:
            d.parent.mkdir(parents=True, exist_ok=True)
            _init_system(d)
            click.echo(f"  System {label}: initialized at {d}")
    click.echo()

    # --- Step 2: Run System A ---
    click.echo("[Step 2] Running System A (intact, recording)...")
    start_time = time.time()
    _run_system(data_a, trios=trios, throttle=throttle, record_path=str(events_path))
    elapsed_a = time.time() - start_time
    click.echo(f"  System A completed in {elapsed_a:.1f}s\n")

    # Verify event log
    if not events_path.exists():
        click.echo("ERROR: Event log not created by System A", err=True)
        sys.exit(1)
    event_count = sum(1 for _ in open(events_path))
    click.echo(f"  Events recorded: {event_count}\n")

    # --- Step 3: Run System B ---
    click.echo("[Step 3] Running System B (ablated, replaying)...")
    start_time = time.time()
    _run_system(data_b, trios=trios, throttle=throttle,
                ablation=True, replay_path=str(events_path))
    elapsed_b = time.time() - start_time
    click.echo(f"  System B completed in {elapsed_b:.1f}s\n")

    # --- Step 4: Compare ---
    click.echo("[Step 4] Generating comparison report...")
    from experiment.analyze import generate_report
    report = generate_report(dir_a, dir_b)

    report_path = out / "report.md"
    report_path.write_text(report)
    click.echo(f"  Report written to {report_path}\n")
    click.echo(report)

    return str(report_path)
