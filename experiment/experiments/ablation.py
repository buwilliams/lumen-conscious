"""Reflexivity ablation experiment.

Disables reflection in System B and measures divergence from intact System A.
"""

import sys
import time
from pathlib import Path

import click

from experiment import Experiment, register


def run_ablation(output_dir: Path, *, trios: int = 300, throttle: int = 300, timeout_ms: int | None = None) -> str:
    """Orchestrate the full ablation experiment.

    1. Create two data directories, init each.
    2. Run System A with recording.
    3. Run System B with replay + ablation.
    4. Generate comparison report.
    """
    from experiment.runner import _init_system, _run_system
    from experiment.analyze import generate_report

    dir_a = output_dir / "system-a"
    dir_b = output_dir / "system-b"
    data_a = dir_a / "data"
    data_b = dir_b / "data"
    events_path = output_dir / "events.jsonl"

    click.echo(f"\n{'='*60}")
    click.echo(f"  Reflexivity Ablation Experiment")
    click.echo(f"  Trios: {trios}, Throttle: {throttle}s")
    click.echo(f"  Output: {output_dir.absolute()}")
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
    report = generate_report(dir_a, dir_b)

    report_path = output_dir / "report.md"
    report_path.write_text(report)
    click.echo(f"  Report written to {report_path}\n")
    click.echo(report)

    return str(report_path)


def compare_ablation(output_dir: Path, output: str | None = None):
    """Generate comparison report for an existing ablation experiment."""
    from experiment.analyze import generate_report

    dir_a = output_dir / "system-a"
    dir_b = output_dir / "system-b"

    if not dir_a.exists() or not dir_b.exists():
        click.echo(f"Error: Expected system-a/ and system-b/ in {output_dir}", err=True)
        sys.exit(1)

    report = generate_report(dir_a, dir_b)
    if output:
        Path(output).write_text(report)
        click.echo(f"Report written to {output}")
    else:
        click.echo(report)


register(Experiment(
    name="ablation",
    description="Reflexivity ablation — disable reflection, measure divergence",
    run=run_ablation,
    compare=compare_ablation,
    cli_run_params=[
        click.Option(["--trios"], type=int, default=300, help="Number of trios to run"),
        click.Option(["--throttle"], type=int, default=300, help="Seconds between trios"),
        click.Option(["--timeout-ms"], type=int, default=None, help="Timeout in milliseconds"),
    ],
))
