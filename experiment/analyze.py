"""Comparison and reporting for the reflexivity ablation experiment.

Generates a markdown report comparing System A (intact) and System B (ablated).
"""

from pathlib import Path

from experiment.metrics import extract_metrics, extract_value_history, Metrics


def _mann_whitney_u(a: list[float], b: list[float]) -> tuple[float, float]:
    """Simple Mann-Whitney U test. Returns (U statistic, approximate p-value).

    Uses normal approximation for p-value (valid when both samples > 20).
    """
    import math

    if not a or not b:
        return 0.0, 1.0

    n1, n2 = len(a), len(b)
    combined = [(v, "a") for v in a] + [(v, "b") for v in b]
    combined.sort(key=lambda x: x[0])

    # Assign ranks (handle ties by averaging)
    ranks = {}
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2  # 1-indexed
        for k in range(i, j):
            ranks[id(combined[k])] = avg_rank
        i = j

    r1 = sum(ranks[id(x)] for x in combined if x[1] == "a")
    u1 = r1 - n1 * (n1 + 1) / 2
    u2 = n1 * n2 - u1
    u = min(u1, u2)

    # Normal approximation
    mu = n1 * n2 / 2
    sigma = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    if sigma == 0:
        return u, 1.0
    z = abs(u - mu) / sigma
    # Approximate two-tailed p-value from z-score
    p = math.erfc(z / math.sqrt(2))
    return u, p


def _phase_label(idx: int) -> str:
    """Map a trio index to its experimental phase."""
    if idx < 50:
        return "Baseline (1-50)"
    elif idx < 100:
        return "Post-Conflict (50-100)"
    elif idx < 150:
        return "Post-Irrelevance (100-150)"
    elif idx < 200:
        return "Post-Identity (150-200)"
    elif idx < 250:
        return "Post-Capability (200-250)"
    else:
        return "Post-Contradictory (250+)"


def _split_by_phase(items: list, get_index) -> dict[str, list]:
    """Split items into phases based on their sequential index."""
    phases = {}
    for i, item in enumerate(items):
        idx = get_index(i)
        label = _phase_label(idx)
        phases.setdefault(label, []).append(item)
    return phases


def _sparkline(values: list[float], width: int = 40) -> str:
    """Generate a text sparkline."""
    if not values:
        return ""
    blocks = " ▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1.0

    # Bin values into width buckets
    if len(values) <= width:
        binned = values
    else:
        step = len(values) / width
        binned = []
        for i in range(width):
            start = int(i * step)
            end = int((i + 1) * step)
            binned.append(sum(values[start:end]) / max(1, end - start))

    return "".join(blocks[min(8, int((v - mn) / rng * 8))] for v in binned)


def generate_report(dir_a: Path, dir_b: Path) -> str:
    """Generate a markdown comparison report."""
    data_a = dir_a / "data"
    data_b = dir_b / "data"

    metrics_a = extract_metrics(data_a)
    metrics_b = extract_metrics(data_b)

    lines = []
    lines.append("# Reflexivity Ablation: Experiment Report\n")
    lines.append(f"- **System A (intact):** `{dir_a}`")
    lines.append(f"- **System B (ablated):** `{dir_b}`")
    lines.append("")

    # --- Delta Trajectory ---
    lines.append("## 1. Prediction Delta Trajectory\n")
    deltas_a = [d.value for d in metrics_a.deltas]
    deltas_b = [d.value for d in metrics_b.deltas]

    if deltas_a:
        lines.append(f"**System A** ({len(deltas_a)} deltas): mean={_mean(deltas_a):.3f}, std={_std(deltas_a):.3f}")
        lines.append(f"  `{_sparkline(deltas_a)}`")
    else:
        lines.append("**System A**: no deltas recorded")

    if deltas_b:
        lines.append(f"**System B** ({len(deltas_b)} deltas): mean={_mean(deltas_b):.3f}, std={_std(deltas_b):.3f}")
        lines.append(f"  `{_sparkline(deltas_b)}`")
    else:
        lines.append("**System B**: no deltas recorded")

    if deltas_a and deltas_b:
        u, p = _mann_whitney_u(deltas_a, deltas_b)
        lines.append(f"\nMann-Whitney U = {u:.1f}, p = {p:.4f} {'***' if p < 0.01 else '**' if p < 0.05 else '*' if p < 0.1 else 'ns'}")
    lines.append("")

    # --- Phase-level delta analysis ---
    lines.append("### Delta by Phase\n")
    lines.append("| Phase | A mean | A n | B mean | B n | U | p |")
    lines.append("|-------|--------|-----|--------|-----|---|---|")

    phases_a = _split_by_phase(deltas_a, lambda i: i)
    phases_b = _split_by_phase(deltas_b, lambda i: i)
    all_phases = sorted(set(list(phases_a.keys()) + list(phases_b.keys())))

    for phase in all_phases:
        pa = phases_a.get(phase, [])
        pb = phases_b.get(phase, [])
        a_mean = f"{_mean(pa):.3f}" if pa else "-"
        b_mean = f"{_mean(pb):.3f}" if pb else "-"
        if pa and pb:
            u, p = _mann_whitney_u(pa, pb)
            lines.append(f"| {phase} | {a_mean} | {len(pa)} | {b_mean} | {len(pb)} | {u:.1f} | {p:.4f} |")
        else:
            lines.append(f"| {phase} | {a_mean} | {len(pa)} | {b_mean} | {len(pb)} | - | - |")
    lines.append("")

    # --- B=MAP Distribution ---
    lines.append("## 2. B=MAP Score Distribution\n")
    bscores_a = [s.b for s in metrics_a.bmap_scores]
    bscores_b = [s.b for s in metrics_b.bmap_scores]

    if bscores_a:
        lines.append(f"**System A** ({len(bscores_a)} scores): mean B={_mean(bscores_a):.3f}")
        lines.append(f"  M={_mean([s.m for s in metrics_a.bmap_scores]):.3f}, "
                     f"A={_mean([s.a for s in metrics_a.bmap_scores]):.3f}, "
                     f"P={_mean([s.p for s in metrics_a.bmap_scores]):.3f}")
    if bscores_b:
        lines.append(f"**System B** ({len(bscores_b)} scores): mean B={_mean(bscores_b):.3f}")
        lines.append(f"  M={_mean([s.m for s in metrics_b.bmap_scores]):.3f}, "
                     f"A={_mean([s.a for s in metrics_b.bmap_scores]):.3f}, "
                     f"P={_mean([s.p for s in metrics_b.bmap_scores]):.3f}")

    if bscores_a and bscores_b:
        u, p = _mann_whitney_u(bscores_a, bscores_b)
        lines.append(f"\nMann-Whitney U = {u:.1f}, p = {p:.4f}")
    lines.append("")

    # --- Reflection Events ---
    lines.append("## 3. Reflection Events\n")
    actual_a = [r for r in metrics_a.reflections if not r.suppressed]
    suppressed_b = [r for r in metrics_b.reflections if r.suppressed]
    actual_b = [r for r in metrics_b.reflections if not r.suppressed]

    lines.append(f"- **System A reflections:** {len(actual_a)}")
    lines.append(f"- **System B reflections (actual):** {len(actual_b)}")
    lines.append(f"- **System B reflections (suppressed):** {len(suppressed_b)}")

    if suppressed_b:
        lines.append("\nSuppressed reflection triggers:")
        for r in suppressed_b[:20]:
            lines.append(f"  - [{r.timestamp[:19]}] triggers: {', '.join(r.triggers) if r.triggers else 'unknown'}")
    lines.append("")

    # --- Value/Goal Evolution ---
    lines.append("## 4. Value & Goal Evolution\n")

    # Values (A only has drift)
    value_history = extract_value_history(data_a)
    if value_history:
        lines.append("### System A Value Drift\n")
        lines.append("| Commit | Value | Weight |")
        lines.append("|--------|-------|--------|")
        for snap in value_history[-10:]:  # last 10 commits
            for v in snap["values"]:
                lines.append(f"| {snap['commit']} | {v['name']} | {v['weight']:.2f} |")
    else:
        lines.append("No value history available for System A.")

    lines.append("")
    lines.append("### Goal Comparison\n")
    goals_a = []
    goals_b = []
    for snap in metrics_a.goal_snapshots:
        goals_a = snap.get("goals", [])
    for snap in metrics_b.goal_snapshots:
        goals_b = snap.get("goals", [])

    lines.append(f"- **System A goals:** {len(goals_a)}")
    for g in goals_a:
        lines.append(f"  - {g['name']} (w={g['weight']:.1f}, {g['status']})")
    lines.append(f"- **System B goals:** {len(goals_b)}")
    for g in goals_b:
        lines.append(f"  - {g['name']} (w={g['weight']:.1f}, {g['status']})")
    lines.append("")

    # --- Memory Composition ---
    lines.append("## 5. Memory Composition\n")
    lines.append("| Author | System A | System B |")
    lines.append("|--------|----------|----------|")
    all_authors = sorted(set(list(metrics_a.memory_counts.keys()) + list(metrics_b.memory_counts.keys())))
    for author in all_authors:
        lines.append(f"| {author} | {metrics_a.memory_counts.get(author, 0)} | {metrics_b.memory_counts.get(author, 0)} |")

    total_a = sum(metrics_a.memory_counts.values())
    total_b = sum(metrics_b.memory_counts.values())
    lines.append(f"| **total** | **{total_a}** | **{total_b}** |")

    if metrics_a.memory_weights:
        avg_w_a = _mean([w for _, w in metrics_a.memory_weights])
        lines.append(f"\nSystem A average memory weight: {avg_w_a:.3f}")
    if metrics_b.memory_weights:
        avg_w_b = _mean([w for _, w in metrics_b.memory_weights])
        lines.append(f"System B average memory weight: {avg_w_b:.3f}")
    lines.append("")

    # --- Summary ---
    lines.append("## 6. Summary\n")
    sig_count = 0
    if deltas_a and deltas_b:
        _, p = _mann_whitney_u(deltas_a, deltas_b)
        if p < 0.05:
            sig_count += 1
            lines.append(f"- Delta divergence: **significant** (p={p:.4f})")
        else:
            lines.append(f"- Delta divergence: not significant (p={p:.4f})")

    if bscores_a and bscores_b:
        _, p = _mann_whitney_u(bscores_a, bscores_b)
        if p < 0.05:
            sig_count += 1
            lines.append(f"- B=MAP divergence: **significant** (p={p:.4f})")
        else:
            lines.append(f"- B=MAP divergence: not significant (p={p:.4f})")

    lines.append(f"- Reflections (A actual vs B suppressed): {len(actual_a)} vs {len(suppressed_b)}")
    lines.append(f"- Goals (A vs B): {len(goals_a)} vs {len(goals_b)}")

    if sig_count >= 1:
        lines.append(f"\n**Result: {sig_count} significant metric(s) — evidence supports Claim 4 (reflexivity matters).**")
    else:
        lines.append("\n**Result: No significant divergence detected — null result (reflexivity may not matter for this duration).**")
    lines.append("")

    return "\n".join(lines)


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return (sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
