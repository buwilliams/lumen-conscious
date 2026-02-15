import subprocess
import time
from datetime import date, datetime

import click


def _auto_commit(trio: int):
    """Commit all data/ changes after a trio completes."""
    try:
        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "status", "--porcelain", "data/"],
            capture_output=True, text=True,
        )
        if not result.stdout.strip():
            return

        subprocess.run(["git", "add", "data/"], check=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(
            ["git", "commit", "-m", f"Auto-commit after trio {trio} ({timestamp})"],
            check=True, capture_output=True,
        )
        click.echo(f"  [git] Committed data/ changes")
    except subprocess.CalledProcessError:
        click.echo(f"  [git] Commit failed (non-fatal)", err=True)


@click.group(context_settings={"max_content_width": 120})
def cli():
    """Lumen — a consciousness architecture."""
    pass


@cli.command()
def init():
    """Scaffold a new Lumen instance."""
    from kernel.init import scaffold
    scaffold()


@cli.command()
@click.option("--session", type=str, help="Resume a conversation session by ID")
def chat(session):
    """Start a conversation."""
    from kernel.chat import ChatSession
    from prompt_toolkit import PromptSession

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
def run(timeout):
    """Start the internal loop (action → explore → reflect cycles)."""
    from kernel.loop_action import run_action_loop
    from kernel.loop_exploration import run_explore_loop
    from kernel.loop_reflection import should_reflect, run_reflection_loop
    from kernel.config import load_config

    config = load_config()
    run_config = config.get("run", {})

    if timeout is None:
        timeout = run_config.get("timeout_ms")

    throttle = run_config.get("throttle_seconds", 900)
    timeout_seconds = timeout / 1000.0 if timeout else None
    start = time.time()

    if timeout_seconds:
        click.echo(f"Lumen internal loop started (timeout: {timeout_seconds:.0f}s, throttle: {throttle}s). Ctrl+C to stop.\n")
    else:
        click.echo(f"Lumen internal loop started (throttle: {throttle}s). Ctrl+C to stop.\n")
    trio = 0
    cycles_since_reflection = 0
    recent_deltas = []

    try:
        while timeout_seconds is None or time.time() - start < timeout_seconds:
            trio += 1

            # --- Action ---
            click.echo(f"[trio {trio}] Running action loop...")
            result = run_action_loop()
            delta = result.get("delta", 0.0)
            recent_deltas.append(delta)
            if len(recent_deltas) > 10:
                recent_deltas = recent_deltas[-10:]
            click.echo(f"  action: {result.get('action', 'none')}")
            click.echo(f"  delta: {delta}")
            cycles_since_reflection += 1

            # --- Explore ---
            click.echo(f"[trio {trio}] Running explore loop...")
            result = run_explore_loop()
            click.echo(f"  question: {result.get('question', 'none')[:200]}")
            cycles_since_reflection += 1

            # --- Reflect ---
            trigger = should_reflect(cycles_since_reflection, recent_deltas)
            if trigger.get("should_reflect"):
                click.echo(f"[trio {trio}] Running reflection loop...")
                click.echo(f"  triggers: {trigger.get('triggers', [])}")
                ref_result = run_reflection_loop(trigger.get("triggers", []))
                changes = ref_result.get("changes", [])
                click.echo(f"  {len(changes)} changes applied")
                cycles_since_reflection = 0
                recent_deltas = []
            else:
                click.echo(f"[trio {trio}] Reflection skipped (no triggers)")

            # --- Commit & Throttle ---
            _auto_commit(trio)
            click.echo(f"\n[trio {trio}] Complete. Waiting {throttle}s before next trio...\n")
            time.sleep(throttle)

    except KeyboardInterrupt:
        _auto_commit(trio)

    elapsed = time.time() - start
    click.echo(f"\nStopped after {trio} trios ({elapsed:.1f}s elapsed).")


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
    if goals:
        for g in sorted(goals, key=lambda x: x.weight, reverse=True):
            click.echo(f"  {g.name:<30} weight={g.weight:.1f}  status={g.status}")
    else:
        click.echo("  (none)")
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
