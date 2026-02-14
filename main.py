import time
from datetime import date

import click


@click.group()
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

    s = ChatSession(session_id=session)
    click.echo(f"Lumen chat (session: {s.session_id})")
    click.echo("Type 'exit' or Ctrl+C to quit.\n")

    try:
        while True:
            try:
                user_input = input("you: ")
            except EOFError:
                break
            if user_input.strip().lower() in ("exit", "quit"):
                break
            if not user_input.strip():
                continue
            response = s.turn(user_input)
            click.echo(f"lumen: {response}\n")
    except KeyboardInterrupt:
        click.echo("\n")

    click.echo(f"Session saved: {s.session_id}")


@cli.command()
def run():
    """Start the internal loop (action + explore cycles)."""
    from kernel.loops import run_action_loop, run_explore_loop
    from kernel.reflection import should_reflect, run_reflection_loop

    click.echo("Lumen internal loop started. Ctrl+C to stop.\n")
    cycle = 0
    cycles_since_reflection = 0
    recent_deltas = []

    try:
        while True:
            cycle += 1

            if cycle % 2 == 1:
                # Action loop
                click.echo(f"[cycle {cycle}] Running action loop...")
                result = run_action_loop()
                delta = result.get("delta", 0.0)
                recent_deltas.append(delta)
                if len(recent_deltas) > 10:
                    recent_deltas = recent_deltas[-10:]
                click.echo(f"  action: {result.get('action', 'none')}")
                click.echo(f"  delta: {delta}")
            else:
                # Explore loop
                click.echo(f"[cycle {cycle}] Running explore loop...")
                result = run_explore_loop()
                click.echo(f"  question: {result.get('question', 'none')}")

            cycles_since_reflection += 1

            # Check reflection trigger after action loops
            if cycle % 2 == 1:
                trigger = should_reflect(cycles_since_reflection, recent_deltas)
                if trigger.get("should_reflect"):
                    click.echo(f"\n[reflection triggered] {trigger.get('triggers', [])}")
                    ref_result = run_reflection_loop(trigger.get("triggers", []))
                    changes = ref_result.get("changes", [])
                    click.echo(f"  {len(changes)} changes applied")
                    cycles_since_reflection = 0
                    recent_deltas = []

            click.echo()
            time.sleep(2)

    except KeyboardInterrupt:
        click.echo(f"\nStopped after {cycle} cycles.")


@cli.command()
@click.option("--trigger", multiple=True, help="Specify trigger reasons")
def reflect(trigger):
    """Manually trigger the reflection loop."""
    from kernel.reflection import run_reflection_loop

    triggers = list(trigger) if trigger else ["explicit"]
    click.echo(f"Running reflection loop (triggers: {triggers})...\n")
    result = run_reflection_loop(triggers)

    review = result.get("review", {})
    click.echo(f"Review: {review.get('summary', 'No summary')[:200]}")
    click.echo()

    changes = result.get("changes", [])
    if changes:
        click.echo(f"{len(changes)} changes applied:")
        for c in changes:
            click.echo(f"  - {c.get('type')}: {c.get('target')} → {c.get('new_value')}")
    else:
        click.echo("No changes proposed.")

    conflicts = result.get("conflicts", [])
    if conflicts:
        click.echo(f"\n{len(conflicts)} conflicts resolved:")
        for c in conflicts:
            click.echo(f"  - {c.get('description')}")


@cli.command()
def status():
    """Print current state."""
    from kernel import data

    soul = data.read_soul()
    values = data.read_values()
    goals = data.read_goals()
    memories = data.read_memories(all_memories=True)

    # Soul summary (first paragraph)
    soul_lines = [l for l in soul.strip().split("\n") if l.strip()]
    soul_summary = soul_lines[0] if soul_lines else "(no soul)"
    click.echo(f"Soul: {soul_summary}")
    click.echo()

    # Values
    click.echo("Values:")
    active = [v for v in values if v.status == "active"]
    if active:
        for v in sorted(active, key=lambda x: x.weight, reverse=True):
            bar = "█" * int(v.weight * 10) + "░" * (10 - int(v.weight * 10))
            click.echo(f"  {v.name:<20} {bar} {v.weight:.1f}")
    else:
        click.echo("  (none)")
    click.echo()

    # Goals
    click.echo("Goals:")
    if goals:
        for g in sorted(goals, key=lambda x: x.weight, reverse=True):
            click.echo(f"  {g.name:<30} weight={g.weight:.1f}  status={g.status}")
    else:
        click.echo("  (none)")
    click.echo()

    # Memory counts
    by_author = {}
    for m in memories:
        by_author[m.author] = by_author.get(m.author, 0) + 1
    click.echo(f"Memories: {len(memories)} total")
    for author, count in sorted(by_author.items()):
        click.echo(f"  {author}: {count}")


@cli.command()
@click.option("--author", type=click.Choice(["self", "kernel", "goal", "external"]))
@click.option("--date", "date_str", type=str, help="Filter by date (YYYY-MM-DD)")
@click.option("--all", "show_all", is_flag=True, help="Show all memories")
def memory(author, date_str, show_all):
    """View recent memories."""
    from kernel import data

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
        return

    click.echo(f"Showing {len(memories)} memories:\n")
    for m in memories:
        ts = m.timestamp[:19]
        click.echo(f"[{ts}] ({m.author}, w={m.weight:.1f})")
        click.echo(f"  {m.description[:200]}")
        click.echo()


@cli.command()
def values():
    """List current values."""
    from kernel import data

    vals = data.read_values()
    if not vals:
        click.echo("No values defined.")
        return

    for v in sorted(vals, key=lambda x: x.weight, reverse=True):
        bar = "█" * int(v.weight * 10) + "░" * (10 - int(v.weight * 10))
        click.echo(f"  {v.name:<20} {bar} {v.weight:.1f}  [{v.status}]")


@cli.command()
@click.option("--year", type=int, help="Filter by year")
@click.option("--status", "goal_status", type=click.Choice(["todo", "working", "done", "perpetual"]))
def goals(year, goal_status):
    """List current goals."""
    from kernel import data

    all_goals = data.read_goals(year=year)
    if goal_status:
        all_goals = [g for g in all_goals if g.status == goal_status]

    if not all_goals:
        click.echo("No goals found.")
        return

    for g in sorted(all_goals, key=lambda x: x.weight, reverse=True):
        click.echo(f"  {g.name:<30} weight={g.weight:.1f}  status={g.status}")


@cli.command()
def skills():
    """List available skills."""
    from kernel import data

    skill_names = data.list_skills()
    if not skill_names:
        click.echo("No skills installed.")
        return

    for name in skill_names:
        click.echo(f"  {name}/")
