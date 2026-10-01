"""Resolve Granit product groups into super-group keys (seed + runtime)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

SEED_PATH = Path(__file__).resolve().parent / "seed" / "supergroups.json"
CATCHALL_KEY = "outside"
SKIP_MEMBERSHIP_KEYS = frozenset({"unclassified", "exclude", CATCHALL_KEY})


@dataclass(frozen=True)
class SeedConfig:
    unmapped_key: str
    exclude_key: str
    catchall_key: str
    catchall_title: str
    catchall_color: str
    catalog: list[dict]
    by_group_id: dict[int, str]
    by_parent_path_prefix: tuple[tuple[str, str], ...]
    by_ancestor_id: dict[int, str]


def _norm_path(path: str) -> str:
    return " ".join(str(path or "").strip().lower().split())


def load_seed_config(path: Path | None = None) -> SeedConfig:
    raw = json.loads((path or SEED_PATH).read_text(encoding="utf-8"))
    catchall = raw.get("catchall") or {}
    rules = raw.get("rules") or {}
    prefixes_raw = rules.get("by_parent_path_prefix") or {}
    prefixes = tuple(
        sorted(
            ((_norm_path(str(p)), str(key)) for p, key in prefixes_raw.items()),
            key=lambda item: len(item[0]),
            reverse=True,
        )
    )
    by_group_id = {int(k): str(v) for k, v in (rules.get("by_group_id") or {}).items()}
    by_ancestor_id = {int(k): str(v) for k, v in (rules.get("by_ancestor_id") or {}).items()}
    return SeedConfig(
        unmapped_key=str(raw.get("unmapped_key") or "unclassified"),
        exclude_key=str(raw.get("exclude_key") or "exclude"),
        catchall_key=str(catchall.get("key") or CATCHALL_KEY),
        catchall_title=str(catchall.get("title") or "Outside super-groups"),
        catchall_color=str(catchall.get("color") or "FFFF00").lstrip("#"),
        catalog=list(raw.get("supergroups") or []),
        by_group_id=by_group_id,
        by_parent_path_prefix=prefixes,
        by_ancestor_id=by_ancestor_id,
    )


def ancestor_chain(group_id: int, parents: Mapping[int, int | None]) -> list[int]:
    out: list[int] = []
    seen: set[int] = {group_id}
    current = parents.get(group_id)
    while current is not None and current not in seen:
        seen.add(current)
        out.append(current)
        current = parents.get(current)
    return out


def resolve_supergroup_key(
    group_id: int,
    parent_path: str,
    *,
    parents: Mapping[int, int | None] | None = None,
    config: SeedConfig | None = None,
) -> str:
    cfg = config or load_seed_config()
    if group_id in cfg.by_group_id:
        return cfg.by_group_id[group_id]
    path_n = _norm_path(parent_path)
    if path_n:
        for prefix, key in cfg.by_parent_path_prefix:
            if path_n == prefix or path_n.startswith(prefix + " >") or path_n.startswith(prefix + ">"):
                return key
            if path_n.startswith(prefix + " "):
                return key
    if parents and cfg.by_ancestor_id:
        for ancestor in ancestor_chain(group_id, parents):
            if ancestor in cfg.by_ancestor_id:
                return cfg.by_ancestor_id[ancestor]
    return cfg.unmapped_key


def build_parent_path(group_id: int, names: Mapping[int, str], parents: Mapping[int, int | None]) -> str:
    parts: list[str] = []
    seen: set[int] = set()
    current: int | None = group_id
    while current is not None and current not in seen:
        seen.add(current)
        parts.append(names.get(current) or f"#{current}")
        current = parents.get(current)
    parts.reverse()
    return " > ".join(parts)
