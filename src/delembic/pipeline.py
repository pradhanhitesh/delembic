from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

from delembic.config import Config


@dataclass
class Step:
    name: str
    type: Literal["alembic", "delembic"]
    target: str = "head"


@dataclass
class Pipeline:
    steps: list[Step] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: Path) -> "Pipeline":
        raw = yaml.safe_load(path.read_text())
        if not isinstance(raw, dict) or "steps" not in raw:
            raise ValueError(f"pipeline file must have a top-level 'steps' list: {path}")
        steps = []
        for i, item in enumerate(raw["steps"]):
            if "type" not in item:
                raise ValueError(f"step {i} missing 'type' (alembic or delembic)")
            steps.append(
                Step(
                    name=item.get("name", f"step-{i}"),
                    type=item["type"],
                    target=item.get("target", "head"),
                )
            )
        return cls(steps=steps)


def run_pipeline(pipeline: Pipeline, cfg: Config) -> None:
    import click

    total = len(pipeline.steps)
    for idx, step in enumerate(pipeline.steps, 1):
        click.echo(f"\n[{idx}/{total}] {step.name}  ({step.type} → {step.target})")
        t0 = time.monotonic()
        if step.type == "alembic":
            _run_alembic_step(step, cfg)
        elif step.type == "delembic":
            _run_delembic_step(step, cfg)
        else:
            raise ValueError(f"Unknown step type: {step.type!r}")
        elapsed = time.monotonic() - t0
        click.echo(f"    done in {elapsed:.1f}s")

    click.echo(f"\nPipeline complete — {total} step(s) ran.")


def _run_alembic_step(step: Step, cfg: Config) -> None:
    if cfg.alembic_config is None:
        raise RuntimeError(
            "alembic step requires alembic_config set in delembic.ini"
        )
    try:
        from alembic import command as alembic_command
        from alembic.config import Config as AlembicConfig
    except ImportError as e:
        raise RuntimeError("alembic not installed — pip install alembic") from e

    alembic_cfg = AlembicConfig(str(cfg.alembic_config), ini_section=cfg.alembic_section)
    alembic_command.upgrade(alembic_cfg, step.target)


def _run_delembic_step(step: Step, cfg: Config) -> None:
    from delembic.executor import run_upgrade

    engine = cfg.engine()
    run_upgrade(
        engine, cfg.versions_dir, step.target,
        alembic_ini=cfg.alembic_config, project_root=cfg.ini_path.parent,
        alembic_section=cfg.alembic_section,
    )
