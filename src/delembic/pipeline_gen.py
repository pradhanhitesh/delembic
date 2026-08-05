"""Auto-generate a Pipeline by reading alembic + delembic dependency graphs."""
from __future__ import annotations

from pathlib import Path

from delembic.config import Config
from delembic.dag import topological_sort
from delembic.pipeline import Pipeline, Step
from delembic.registry import load_migrations


def generate_pipeline(cfg: Config) -> Pipeline:
    """
    Introspect alembic revision chain and delembic depends_on to build an
    interleaved pipeline that applies schema and data migrations in the correct order.
    """
    if cfg.alembic_config is None:
        raise RuntimeError(
            "Cannot auto-generate pipeline: alembic_config not set in delembic.ini. "
            "Set alembic_config = alembic.ini and try again."
        )

    alembic_chain = _get_alembic_chain(cfg.alembic_config)
    alembic_pos = {rev: i for i, rev in enumerate(alembic_chain)}

    migrations = load_migrations(cfg.versions_dir, cfg.ini_path.parent)
    if not migrations:
        # No delembic migrations yet — simple single alembic step
        return Pipeline(steps=[Step(name="Schema → head", type="alembic", target="head")])

    delembic_order = topological_sort(migrations)

    # For each delembic migration, find the latest alembic revision it depends on.
    # "Latest" = highest position in the alembic chain.
    def latest_alembic_checkpoint(delembic_rev: str) -> str | None:
        cls = migrations[delembic_rev]
        external_deps = [dep for dep in cls.depends_on if dep not in migrations]
        if not external_deps:
            return None
        known = [dep for dep in external_deps if dep in alembic_pos]
        if not known:
            return None
        return max(known, key=lambda r: alembic_pos[r])

    # Group delembic revisions by their required alembic checkpoint.
    # None means "no alembic dependency" → run at the end after all schema.
    groups: dict[str | None, list[str]] = {}
    for dr in delembic_order:
        cp = latest_alembic_checkpoint(dr)
        groups.setdefault(cp, []).append(dr)

    checkpoints_needed: set[str] = {cp for cp in groups if cp is not None}

    steps: list[Step] = []

    # Walk alembic chain and emit a checkpoint block wherever delembic migrations wait.
    for alembic_rev in alembic_chain:
        if alembic_rev not in checkpoints_needed:
            continue

        steps.append(Step(
            name=f"Schema → {alembic_rev}",
            type="alembic",
            target=alembic_rev,
        ))
        for dm_rev in groups[alembic_rev]:
            steps.append(Step(
                name=f"Data: {migrations[dm_rev].description}",
                type="delembic",
                target=dm_rev,
            ))

    # Always finish with alembic → head and delembic → head.
    # Handles: remaining schema, no-dep delembic migrations, idempotent reruns.
    steps.append(Step(name="Schema → head", type="alembic", target="head"))
    steps.append(Step(name="Data migrations → head", type="delembic", target="head"))

    return Pipeline(steps=steps)


def pipeline_to_yaml(pipeline: Pipeline) -> str:
    import yaml

    data = {
        "steps": [
            {"name": s.name, "type": s.type, "target": s.target}
            for s in pipeline.steps
        ]
    }
    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _get_alembic_chain(alembic_ini: Path) -> list[str]:
    """Return all alembic revision IDs in order from base to head."""
    try:
        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory
    except ImportError:
        raise RuntimeError("alembic not installed — pip install alembic")

    alembic_cfg = AlembicConfig(str(alembic_ini))
    script = ScriptDirectory.from_config(alembic_cfg)

    # iterate_revisions walks head → base; reverse for base → head
    try:
        heads = script.get_heads()
        if not heads:
            return []
        if len(heads) > 1:
            raise RuntimeError(
                f"Alembic has multiple heads {heads}. "
                "Resolve with 'alembic merge heads' before generating a pipeline."
            )
        revisions = list(script.iterate_revisions(heads[0], "base"))
        revisions.reverse()
        return [r.revision for r in revisions]
    except Exception as e:
        raise RuntimeError(f"Could not read alembic revision chain: {e}") from e
