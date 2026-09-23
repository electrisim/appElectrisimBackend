# -*- coding: utf-8 -*-
"""Resolve Electrisim short-circuit fault location: all busbars vs user selection."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Set


def normalize_fault_bus_mode(in_data: Optional[dict]) -> str:
    if not isinstance(in_data, dict):
        return "all"
    raw = in_data.get("fault_bus_mode") or in_data.get("fault_location_scope") or "all"
    mode = str(raw or "all").strip().lower().replace("-", "_").replace(" ", "_")
    if mode in ("selection", "user", "user_selection", "selected", "userselection"):
        return "selection"
    return "all"


def _as_ref_list(value: Any) -> List[str]:
    if value is None or value is False:
        return []
    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = [p.strip() for p in str(value).replace(";", ",").split(",")]
    out: List[str] = []
    for item in items:
        s = str(item).strip()
        if s and s.lower() not in ("none", "null", "undefined"):
            out.append(s)
    return out


def collect_fault_bus_refs(in_data: Optional[dict]) -> List[str]:
    if not isinstance(in_data, dict):
        return []
    refs: List[str] = []
    for key in ("fault_bus_ids", "fault_buses", "fault_bus_names", "fault_bus_id"):
        for item in _as_ref_list(in_data.get(key)):
            if item not in refs:
                refs.append(item)
    return refs


def _norm(s: Any) -> str:
    return str(s).strip().replace("#", "_").lower()


def _aliases(value: Any) -> Set[str]:
    if value is None:
        return set()
    raw = str(value).strip()
    if not raw:
        return set()
    variants = {raw, raw.replace("#", "_"), raw.replace("_", "#")}
    stripped = raw.lstrip("#_")
    if stripped and stripped != raw:
        variants.add(stripped)
        variants.add("_" + stripped)
        variants.add("#" + stripped)
    return {_norm(v) for v in variants if str(v).strip()}


def refs_wanted(refs: Sequence[str]) -> Set[str]:
    wanted: Set[str] = set()
    for ref in refs:
        wanted.update(_aliases(ref))
    return wanted


def row_matches_fault_refs(wanted: Set[str], *values: Any) -> bool:
    if not wanted:
        return False
    keys: Set[str] = set()
    for value in values:
        keys.update(_aliases(value))
    return bool(keys & wanted)


def resolve_pp_fault_bus_indices(net, in_data: Optional[dict], Busbars: Optional[dict] = None) -> Optional[List[int]]:
    """Return pandapower bus indices for User Selection, or None for all busbars."""
    if normalize_fault_bus_mode(in_data) != "selection":
        return None
    refs = collect_fault_bus_refs(in_data)
    if not refs:
        raise ValueError(
            "Fault location is User Selection, but no busbars were selected. "
            "Select one or more busbars on the diagram or in the Short Circuit dialog."
        )
    wanted = refs_wanted(refs)
    matched: List[int] = []
    seen: Set[int] = set()
    uf = getattr(net, "user_friendly_names", None) or {}

    bus_table = getattr(net, "bus", None)
    if bus_table is not None and not bus_table.empty:
        for idx, row in bus_table.iterrows():
            name = row["name"] if "name" in row.index else None
            bus_id = row["id"] if "id" in row.index else None
            extra = [uf.get(name), uf.get(str(name))]
            if row_matches_fault_refs(wanted, name, bus_id, idx, *extra):
                bi = int(idx)
                if bi not in seen:
                    seen.add(bi)
                    matched.append(bi)

    if Busbars:
        for key, idx in Busbars.items():
            try:
                bi = int(idx)
            except (TypeError, ValueError):
                continue
            if bi in seen:
                continue
            if row_matches_fault_refs(wanted, key):
                seen.add(bi)
                matched.append(bi)

    if not matched:
        raise ValueError(
            "Fault location is User Selection, but none of the selected busbars "
            "could be matched to the network. Select AC busbars on the diagram."
        )
    return matched


def filter_bus_result_rows(rows: Iterable[dict], in_data: Optional[dict]) -> List[dict]:
    """Keep only selected bus result dicts when mode is User Selection."""
    rows = list(rows or [])
    if normalize_fault_bus_mode(in_data) != "selection":
        return rows
    wanted = refs_wanted(collect_fault_bus_refs(in_data))
    if not wanted:
        return rows
    kept = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row_matches_fault_refs(wanted, row.get("id"), row.get("name"), row.get("userFriendlyName")):
            kept.append(row)
    return kept
