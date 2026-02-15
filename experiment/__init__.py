"""Experiment registry for named experiments."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import click


@dataclass
class Experiment:
    name: str
    description: str
    run: Callable  # (output_dir: Path, **kwargs) -> str (report path)
    compare: Callable  # (output_dir: Path, output: str | None) -> None
    cli_run_params: list[click.Parameter] = field(default_factory=list)


_REGISTRY: dict[str, Experiment] = {}


def register(experiment: Experiment):
    """Register an experiment."""
    _REGISTRY[experiment.name] = experiment


def get(name: str) -> Experiment | None:
    """Get an experiment by name."""
    return _REGISTRY.get(name)


def list_experiments() -> list[Experiment]:
    """List all registered experiments."""
    return list(_REGISTRY.values())


# Auto-import experiment modules to trigger registration
import experiment.experiments.ablation  # noqa: E402, F401
