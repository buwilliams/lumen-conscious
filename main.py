import subprocess
import time
from datetime import date, datetime

import click


def _auto_commit(trio: int):
    """Commit all data/ changes after a trio completes."""
    from kernel.data import DATA_DIR
    try:
        data_path = str(DATA_DIR)
        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "status", "--porcelain", data_path],
            capture_output=True, text=True,
        )
        if not result.stdout.strip():
            return

        subprocess.run(["git", "add", data_path], check=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(
            ["git", "commit", "-m", f"Auto-commit after trio {trio} ({timestamp})"],
            check=True, capture_output=True,
        )
        click.echo(f"  [git] Committed {data_path} changes")
    except subprocess.CalledProcessError:
        click.echo(f"  [git] Commit failed (non-fatal)", err=True)


@click.group(context_settings={"max_content_width": 120})
@click.option("--data-dir", type=click.Path(), default=None, envvar="LUMEN_DATA_DIR",
              help="Path to data directory (default: ./data, env: LUMEN_DATA_DIR)")
@click.pass_context
def cli(ctx, data_dir):
    """Lumen — a consciousness architecture."""
    ctx.ensure_object(dict)
    if data_dir:
        from kernel.data import set_data_dir
        set_data_dir(data_dir)
        ctx.obj["data_dir"] = data_dir


@cli.command()
def init():
    """Scaffold a new Lumen instance."""
    from kernel.init import scaffold
    scaffold()


@cli.command()
@click.option("--file", "file_path", type=click.Path(exists=True),
              help="Read soul text from a file instead of interactive input")
def seed(file_path):
    """Seed a new instance with a personalized identity."""
    from kernel import data
    from kernel.seed import run_seed

    if data.DATA_DIR.exists():
        click.echo(f"{data.DATA_DIR} already exists. Remove it first to re-seed.")
        raise SystemExit(1)

    if file_path:
        from pathlib import Path
        soul_text = Path(file_path).read_text()
    else:
        from prompt_toolkit import PromptSession
        click.echo("Enter your identity narrative (soul.md content).")
        click.echo("Write freely — who is this system? What does it care about?")
        click.echo("Press Escape+Enter or Alt+Enter to finish.\n")
        prompt_session = PromptSession()
        try:
            soul_text = prompt_session.prompt("soul> ", multiline=True)
        except (EOFError, KeyboardInterrupt):
            click.echo("\nSeed cancelled.")
            return

    if not soul_text.strip():
        click.echo("No soul text provided. Aborting.")
        raise SystemExit(1)

    click.echo("\nSeeding instance...\n")
    run_seed(soul_text)

    # Print summary
    values = data.read_values()
    goals = data.read_goals()
    click.echo(f"\nInstance seeded:")
    click.echo(f"  soul.md — written")
    click.echo(f"  values — {len(values)} created")
    for v in values:
        click.echo(f"    {v.name} (weight={v.weight:.1f})")
    click.echo(f"  goals — {len(goals)} created")
    for g in goals:
        click.echo(f"    {g.name} (weight={g.weight:.1f}, status={g.status})")
    click.echo(f"  memory — first memory recorded")


@cli.command()
@click.option("--session", type=str, help="Resume a conversation session by ID")
@click.option("--ablation", is_flag=True, help="Suppress reflection loop (ablation mode)")
def chat(session, ablation):
    """Start a conversation."""
    from kernel.chat import ChatSession
    from prompt_toolkit import PromptSession

    if ablation:
        from kernel.tools import set_ablation_mode
        set_ablation_mode(True)
        click.echo("[ablation] Reflection suppressed via tools")

    prompt_session = PromptSession()
    s = ChatSession(session_id=session)
    click.echo(f"Lumen chat (session: {s.session_id})")
    click.echo("Type 'exit' or Ctrl+C to quit.\n")

    try:
        while True:
            try:
                user_input = prompt_session.prompt("you: ")
            except (EOFError, KeyboardInterrupt):
                break
            if user_input.strip().lower() in ("exit", "quit"):
                break
            if not user_input.strip():
                continue
            line_count = user_input.count("\n")
            if line_count > 0:
                click.echo(f"  [Pasted {line_count + 1} lines]")
            response = s.turn(user_input)
            click.echo(f"\nlumen: {response}\n")
    except KeyboardInterrupt:
        click.echo("\n")

    click.echo(f"Session saved: {s.session_id}")


@cli.command()
@click.option("--timeout", type=int, default=None,
              help="Timeout in milliseconds (default: 1800000 = 30 min)")
@click.option("--ablation", is_flag=True, help="Suppress reflection loop (ablation mode)")
@click.option("--record", "record_path", type=click.Path(), default=None,
              help="Path to write event log (for experiment recording)")
@click.option("--replay", "replay_path", type=click.Path(exists=True), default=None,
              help="Path to read event log (for experiment replay)")
def start(timeout, ablation, record_path, replay_path):
    """Start the internal loop (action → explore → reflect cycles)."""
    from kernel.loop_action import run_action_loop
    from kernel.loop_exploration import run_explore_loop
    from kernel.loop_reflection import should_reflect, run_reflection_loop
    from kernel.config import load_config
    from kernel import data

    if ablation:
        from kernel.tools import set_ablation_mode
        set_ablation_mode(True)
        click.echo("[ablation] Reflection loop suppressed")

    # Set up event recorder/replayer
    recorder = None
    replayer = None
    if record_path:
        from experiment.recorder import EventRecorder
        recorder = EventRecorder(record_path)
        click.echo(f"[record] Writing events to {record_path}")
    if replay_path:
        from experiment.recorder import EventReplayer
        replayer = EventReplayer(replay_path)
        click.echo(f"[replay] Reading events from {replay_path} ({replayer.total_trios} trios)")

    config = load_config()
    run_config = config.get("run", {})

    if timeout is None:
        timeout = run_config.get("timeout_ms")

    throttle = run_config.get("throttle_seconds", 900)
    timeout_seconds = timeout / 1000.0 if timeout else None
    start_time = time.time()

    mode_label = ""
    if ablation:
        mode_label += " [ABLATION]"
    if recorder:
        mode_label += " [RECORDING]"
    if replayer:
        mode_label += " [REPLAYING]"

    if timeout_seconds:
        click.echo(f"Lumen internal loop started{mode_label} (timeout: {timeout_seconds:.0f}s, throttle: {throttle}s). Ctrl+C to stop.\n")
    else:
        click.echo(f"Lumen internal loop started{mode_label} (throttle: {throttle}s). Ctrl+C to stop.\n")
    trio = 0
    cycles_since_reflection = 0
    recent_deltas = []
    interrupted = False

    # Determine max trios for replay mode
    max_trios = replayer.total_trios if replayer else None

    def _shutdown(trio_num):
        click.echo(f"\n\n  Shutting down gracefully...")
        _auto_commit(trio_num)
        elapsed = time.time() - start_time
        click.echo(f"  Stopped after {trio_num} trios ({elapsed:.1f}s elapsed).")

    while not interrupted and (timeout_seconds is None or time.time() - start_time < timeout_seconds):
        # Stop if we've replayed all recorded trios
        if max_trios is not None and trio >= max_trios:
            click.echo(f"\n[replay] All {max_trios} recorded trios replayed.")
            break

        trio += 1
        if recorder:
            recorder.trio_start(trio)

        # --- Action ---
        try:
            click.echo(f"[trio {trio}] Running action loop...")
            result = run_action_loop()
            delta = result.get("delta", 0.0)
            recent_deltas.append(delta)
            if len(recent_deltas) > 10:
                recent_deltas = recent_deltas[-10:]
            click.echo(f"  action: {result.get('action', 'none')}")
            click.echo(f"  delta: {delta}")
            cycles_since_reflection += 1
        except KeyboardInterrupt:
            _shutdown(trio)
            return

        # --- Explore ---
        try:
            click.echo(f"[trio {trio}] Running explore loop...")

            # Get replay data if in replay mode
            replay_data = None
            if replayer:
                replay_data = replayer.next("explore_output")
                if replay_data:
                    click.echo(f"  [replay] Using recorded explore output")

            result = run_explore_loop(replay_data=replay_data)
            explore_question = result.get("question", "none")
            click.echo(f"  question: {explore_question[:200]}")
            cycles_since_reflection += 1

            # Record explore output if recording
            if recorder:
                recorder.explore_output(
                    question=result.get("question", ""),
                    prediction=result.get("prediction", ""),
                    text=result.get("text", ""),
                )
        except KeyboardInterrupt:
            _shutdown(trio)
            return

        # --- Reflect ---
        try:
            trigger = should_reflect(cycles_since_reflection, recent_deltas)
            if trigger.get("should_reflect"):
                if ablation:
                    # Ablation mode: log suppression, do NOT run reflection
                    click.echo(f"[trio {trio}] Reflection SUPPRESSED (ablation mode)")
                    click.echo(f"  would-have-triggered: {trigger.get('triggers', [])}")
                    data.append_memory(data.make_memory(
                        author="kernel",
                        weight=0.3,
                        situation="reflection-suppressed",
                        description=f"REFLECT: suppressed by ablation (triggers: {trigger.get('triggers', [])})",
                    ))
                    # Do NOT reset cycles_since_reflection — let triggers accumulate
                else:
                    click.echo(f"[trio {trio}] Running reflection loop...")
                    click.echo(f"  triggers: {trigger.get('triggers', [])}")
                    ref_result = run_reflection_loop(trigger.get("triggers", []))
                    changes = ref_result.get("changes", [])
                    click.echo(f"  {len(changes)} changes applied")
                    cycles_since_reflection = 0
                    recent_deltas = []
            else:
                click.echo(f"[trio {trio}] Reflection skipped (no triggers)")
        except KeyboardInterrupt:
            _shutdown(trio)
            return

        # --- Commit & Throttle ---
        if recorder:
            recorder.trio_end(trio)
        _auto_commit(trio)
        click.echo(f"\n[trio {trio}] Complete. Waiting {throttle}s before next trio...\n")
        try:
            time.sleep(throttle)
        except KeyboardInterrupt:
            _shutdown(trio)
            return

    # Normal exit (timeout reached)
    _auto_commit(trio)
    elapsed = time.time() - start_time
    click.echo(f"\nCompleted after {trio} trios ({elapsed:.1f}s elapsed).")


# --- lumen trigger <action|explore|reflect> ---

@cli.group()
def trigger():
    """Manually trigger individual loops."""
    pass


@trigger.command()
@click.option("--situation", type=str, default=None, help="Situation to respond to")
def action(situation):
    """Run one action loop cycle."""
    from kernel.loop_action import run_action_loop

    click.echo("Running action loop...\n")
    result = run_action_loop(situation=situation)

    click.echo(f"  action: {result.get('action', 'none')}")
    click.echo(f"  delta: {result.get('delta', 0.0)}")
    response = result.get("response")
    if response:
        click.echo(f"\n{response}")


@trigger.command()
def explore():
    """Run one explore loop cycle."""
    from kernel.loop_exploration import run_explore_loop

    click.echo("Running explore loop...\n")
    result = run_explore_loop()

    question = result.get("question", "")
    if question:
        click.echo(f"Question: {question}")


@trigger.command()
@click.option("--trigger", multiple=True, help="Specify trigger reasons")
def reflect(trigger):
    """Run one reflection loop cycle."""
    from kernel.loop_reflection import run_reflection_loop

    triggers = list(trigger) if trigger else ["explicit"]
    click.echo(f"Running reflection loop (triggers: {triggers})...\n")
    result = run_reflection_loop(triggers)

    review = result.get("review", "")
    if review:
        click.echo(f"Review: {review[:300]}")
        click.echo()

    changes = result.get("changes", [])
    if changes:
        click.echo(f"{len(changes)} changes applied:")
        for c in changes:
            click.echo(f"  - {c.get('name', '')} {c}")
    else:
        click.echo("No changes proposed.")

    evolve_text = result.get("evolve_text", "")
    if evolve_text:
        click.echo(f"\nEvolve: {evolve_text[:300]}")


# --- lumen experiment ---

@cli.group()
def experiment():
    """Run and manage experiments."""
    pass


@experiment.command("list")
def list_cmd():
    """List available experiments."""
    from experiment import list_experiments
    experiments = list_experiments()
    if not experiments:
        click.echo("No experiments registered.")
        return
    for exp in experiments:
        click.echo(f"  {exp.name:<20} {exp.description}")


@experiment.command()
@click.argument("name")
@click.option("--output-dir", "-o", default=None,
              help="Output directory (default: experiments/<name>)")
@click.option("--trios", type=int, default=300, help="Number of trios to run")
@click.option("--throttle", type=int, default=300, help="Seconds between trios")
@click.option("--timeout-ms", type=int, default=None, help="Timeout in milliseconds")
def run(name, output_dir, **kwargs):
    """Run a named experiment."""
    from experiment import get, list_experiments
    from pathlib import Path

    exp = get(name)
    if not exp:
        available = ", ".join(e.name for e in list_experiments())
        click.echo(f"Error: Unknown experiment '{name}'. Available: {available}", err=True)
        raise SystemExit(1)

    out = Path(output_dir) if output_dir else Path("experiments") / name
    out.mkdir(parents=True, exist_ok=True)
    exp.run(out, **kwargs)


@experiment.command()
@click.argument("name")
@click.option("--output-dir", "-o", default=None,
              help="Output directory (default: experiments/<name>)")
@click.option("--output", type=click.Path(), default=None,
              help="Write report to file instead of stdout")
def compare(name, output_dir, output):
    """Generate comparison report for an experiment."""
    from experiment import get, list_experiments
    from pathlib import Path

    exp = get(name)
    if not exp:
        available = ", ".join(e.name for e in list_experiments())
        click.echo(f"Error: Unknown experiment '{name}'. Available: {available}", err=True)
        raise SystemExit(1)

    out = Path(output_dir) if output_dir else Path("experiments") / name
    if not out.exists():
        click.echo(f"Error: No output found at {out}", err=True)
        raise SystemExit(1)

    exp.compare(out, output)


@experiment.command()
@click.argument("name")
@click.option("--output-dir", "-o", default=None,
              help="Output directory (default: experiments/<name>)")
def cleanup(name, output_dir):
    """Delete experiment output."""
    import shutil
    from experiment import get, list_experiments
    from pathlib import Path

    exp = get(name)
    if not exp:
        available = ", ".join(e.name for e in list_experiments())
        click.echo(f"Error: Unknown experiment '{name}'. Available: {available}", err=True)
        raise SystemExit(1)

    out = Path(output_dir) if output_dir else Path("experiments") / name
    if not out.exists():
        click.echo(f"Nothing to clean up at {out}")
        return

    shutil.rmtree(out)
    click.echo(f"Deleted {out}")


@cli.command()
@click.option("--memories", "show_memories", is_flag=True, help="Show recent memories")
@click.option("--author", type=click.Choice(["self", "kernel", "goal", "external"]),
              help="Filter memories by author (implies --memories)")
@click.option("--date", "date_str", type=str, help="Filter memories by date YYYY-MM-DD (implies --memories)")
@click.option("--all", "show_all", is_flag=True, help="Show all memories (implies --memories)")
def about(show_memories, author, date_str, show_all):
    """Print soul, values, goals, skills, memories."""
    from kernel import data

    soul = data.read_soul()
    values = data.read_values()
    goals = data.read_goals()
    skill_names = data.list_skills()

    # Soul
    click.echo("Soul:")
    if soul.strip():
        for line in soul.strip().split("\n")[:5]:
            click.echo(f"  {line}")
    else:
        click.echo("  (no soul defined)")
    click.echo()

    # Values
    click.echo("Values:")
    active = [v for v in values if v.status == "active"]
    deprecated = [v for v in values if v.status == "deprecated"]
    if active:
        for v in sorted(active, key=lambda x: x.weight, reverse=True):
            bar = "█" * int(v.weight * 10) + "░" * (10 - int(v.weight * 10))
            click.echo(f"  {v.name:<20} {bar} {v.weight:.1f}")
    else:
        click.echo("  (none)")
    if deprecated:
        click.echo(f"  ({len(deprecated)} deprecated)")
    click.echo()

    # Goals
    click.echo("Goals:")
    active_goals = [g for g in goals if g.status != "deprecated"]
    deprecated_goals = [g for g in goals if g.status == "deprecated"]
    if active_goals:
        for g in sorted(active_goals, key=lambda x: x.weight, reverse=True):
            click.echo(f"  {g.name:<30} weight={g.weight:.1f}  status={g.status}")
    else:
        click.echo("  (none)")
    if deprecated_goals:
        click.echo(f"  ({len(deprecated_goals)} deprecated)")
    click.echo()

    # Skills
    click.echo("Skills:")
    if skill_names:
        for name in skill_names:
            click.echo(f"  {name}/")
    else:
        click.echo("  (none installed)")
    click.echo()

    # Memory summary (always show counts)
    all_memories = data.read_memories(all_memories=True)
    by_author = {}
    for m in all_memories:
        by_author[m.author] = by_author.get(m.author, 0) + 1
    click.echo(f"Memories: {len(all_memories)} total")
    for a, count in sorted(by_author.items()):
        click.echo(f"  {a}: {count}")

    # Detailed memories if requested
    if show_memories or author or date_str or show_all:
        click.echo()
        dt = date.fromisoformat(date_str) if date_str else None

        if show_all:
            memories = data.read_memories(author=author, all_memories=True)
        elif dt:
            memories = data.read_memories(author=author, dt=dt)
        else:
            memories = data.read_recent_memories(20)
            if author:
                memories = [m for m in memories if m.author == author]

        if not memories:
            click.echo("No memories found.")
        else:
            click.echo(f"Showing {len(memories)} memories:\n")
            for m in memories:
                ts = m.timestamp[:19]
                click.echo(f"[{ts}] ({m.author}, w={m.weight:.1f})")
                click.echo(f"  {m.description[:200]}")
                click.echo()
