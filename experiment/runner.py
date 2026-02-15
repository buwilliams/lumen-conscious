"""Experiment orchestration for the reflexivity ablation study.

Creates two Lumen instances, runs System A with recording, then System B
with replay + ablation, and generates a comparison report.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import click


def _run_lumen(cwd: Path, args: list[str], timeout: int | None = None):
    """Run a lumen command in a given directory."""
    cmd = ["uv", "run", "lumen"] + args
    click.echo(f"  $ {' '.join(cmd)} (in {cwd})")
    result = subprocess.run(
        cmd, cwd=cwd, timeout=timeout,
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        click.echo(f"  STDERR: {result.stderr[:500]}", err=True)
    return result


def run_experiment(
    output_dir: str = "experiment_output",
    trios: int = 300,
    throttle: int = 300,
    timeout_ms: int | None = None,
):
    """Orchestrate the full ablation experiment.

    1. Create two directories (system-a, system-b), run lumen init in each.
    2. Run System A with --record.
    3. Copy events to System B, run with --replay --ablation.
    4. Run comparison.
    """
    out = Path(output_dir)
    dir_a = out / "system-a"
    dir_b = out / "system-b"
    events_file = "events.jsonl"

    # Compute timeout from trios and throttle if not specified
    if timeout_ms is None:
        # Generous: 2x expected time (throttle + ~60s per trio for LLM calls)
        timeout_ms = trios * (throttle + 60) * 2 * 1000

    click.echo(f"\n{'='*60}")
    click.echo(f"  Reflexivity Ablation Experiment")
    click.echo(f"  Trios: {trios}, Throttle: {throttle}s")
    click.echo(f"  Output: {out.absolute()}")
    click.echo(f"{'='*60}\n")

    # --- Step 1: Initialize both systems ---
    click.echo("[Step 1] Initializing both systems...")

    for d in [dir_a, dir_b]:
        if d.exists():
            click.echo(f"  {d} already exists, skipping init")
            continue
        d.mkdir(parents=True, exist_ok=True)

        # Copy project files (not data/) so lumen commands work
        project_root = Path(__file__).resolve().parent.parent
        for item in ["kernel", "skills", "experiment", "main.py", "pyproject.toml", "uv.lock"]:
            src = project_root / item
            dst = d / item
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            elif src.exists():
                shutil.copy2(src, dst)

        # Also copy CLAUDE.md if present
        claude_md = project_root / "CLAUDE.md"
        if claude_md.exists():
            shutil.copy2(claude_md, d / "CLAUDE.md")

        _run_lumen(d, ["init"])

    click.echo("  Both systems initialized.\n")

    # --- Step 2: Run System A ---
    click.echo("[Step 2] Running System A (intact, recording)...")
    a_result = _run_lumen(dir_a, [
        "start",
        "--timeout", str(timeout_ms),
        "--record", events_file,
    ], timeout=timeout_ms // 1000 + 120)
    click.echo(f"  System A completed. stdout: {len(a_result.stdout)} chars\n")

    # Verify event log exists
    a_events = dir_a / events_file
    if not a_events.exists():
        click.echo("ERROR: Event log not created by System A", err=True)
        sys.exit(1)

    event_count = sum(1 for _ in open(a_events))
    click.echo(f"  Events recorded: {event_count}\n")

    # --- Step 3: Copy events and run System B ---
    click.echo("[Step 3] Running System B (ablated, replaying)...")
    b_events = dir_b / events_file
    shutil.copy2(a_events, b_events)

    b_result = _run_lumen(dir_b, [
        "start",
        "--timeout", str(timeout_ms),
        "--replay", events_file,
        "--ablation",
    ], timeout=timeout_ms // 1000 + 120)
    click.echo(f"  System B completed. stdout: {len(b_result.stdout)} chars\n")

    # --- Step 4: Compare ---
    click.echo("[Step 4] Generating comparison report...")
    from experiment.analyze import generate_report
    report = generate_report(dir_a, dir_b)

    report_path = out / "report.md"
    report_path.write_text(report)
    click.echo(f"  Report written to {report_path}\n")
    click.echo(report)

    return str(report_path)
