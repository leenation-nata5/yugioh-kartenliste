# -*- coding: utf-8 -*-
"""Validated offline card-database delta packs with bounded rollback data."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Mapping, Tuple


SCHEMA_VERSION = 1


def _canonical_payload(pack: Mapping[str, Any]) -> bytes:
    safe = {key: value for key, value in dict(pack or {}).items() if key != "checksum"}
    return json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def pack_checksum(pack: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_payload(pack)).hexdigest()


def validate_pack(pack: Mapping[str, Any], *, max_operations: int = 50000) -> Dict[str, Any]:
    if not isinstance(pack, Mapping):
        raise ValueError("Delta-Paket ist kein JSON-Objekt")
    if int(pack.get("schema", 0) or 0) != SCHEMA_VERSION:
        raise ValueError("Nicht unterstützte Delta-Paket-Version")
    pack_id = str(pack.get("pack_id") or "")
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,96}", pack_id):
        raise ValueError("Ungültige Delta-Paket-ID")
    operations = pack.get("operations")
    if not isinstance(operations, list) or len(operations) > max_operations:
        raise ValueError("Ungültige oder zu große Operationsliste")
    expected = str(pack.get("checksum") or "").lower()
    actual = pack_checksum(pack)
    if expected != actual:
        raise ValueError("Prüfsumme des Delta-Pakets stimmt nicht")
    for index, operation in enumerate(operations):
        if not isinstance(operation, Mapping) or operation.get("op") not in {"upsert", "delete"}:
            raise ValueError(f"Operation {index + 1} ist ungültig")
        if operation.get("op") == "upsert" and not isinstance(operation.get("card"), Mapping):
            raise ValueError(f"Operation {index + 1} enthält keine Karte")
    return {
        "pack_id": pack_id,
        "base_version": str(pack.get("base_version") or ""),
        "target_version": str(pack.get("target_version") or ""),
        "language": str(pack.get("language") or "de"),
        "operations": len(operations),
        "checksum": actual,
    }


def _identity(card_or_id: Any) -> str:
    if isinstance(card_or_id, Mapping):
        value = card_or_id.get("id") or card_or_id.get("passcode") or card_or_id.get("name")
    else:
        value = card_or_id
    return str(value or "").strip()


def apply_delta_pack(cards: Iterable[Mapping[str, Any]], pack: Mapping[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    meta = validate_pack(pack)
    current: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for raw_card in cards or []:
        if not isinstance(raw_card, Mapping):
            continue
        card = dict(raw_card)
        key = _identity(card)
        if not key:
            continue
        if key not in current:
            order.append(key)
        current[key] = card

    rollback = {
        "pack_id": meta["pack_id"],
        "language": meta["language"],
        "previous": {},
        "created": [],
        "previous_order": order,
    }
    for operation in pack.get("operations") or []:
        op = str(operation.get("op"))
        key = _identity(operation.get("card") if op == "upsert" else operation.get("id"))
        if not key:
            raise ValueError("Delta-Operation ohne Karten-ID")
        if key in current and key not in rollback["previous"]:
            rollback["previous"][key] = current[key]
        elif key not in current and key not in rollback["created"]:
            rollback["created"].append(key)
        if op == "delete":
            current.pop(key, None)
        else:
            card = dict(operation.get("card") or {})
            current[key] = card
            if key not in order:
                order.append(key)
    output = [current[key] for key in order if key in current]
    # Include any records whose order was not in the original pack/base.
    ordered_keys = set(order)
    output.extend(current[key] for key in current if key not in ordered_keys)
    return output, rollback


def rollback_delta_pack(cards: Iterable[Mapping[str, Any]], rollback: Mapping[str, Any]) -> List[Dict[str, Any]]:
    current = {_identity(card): dict(card) for card in cards or [] if isinstance(card, Mapping) and _identity(card)}
    for key in rollback.get("created") or []:
        current.pop(str(key), None)
    for key, card in (rollback.get("previous") or {}).items():
        if isinstance(card, Mapping):
            current[str(key)] = dict(card)
    order = [str(key) for key in rollback.get("previous_order") or []]
    output = [current[key] for key in order if key in current]
    seen = set(order)
    output.extend(card for key, card in current.items() if key not in seen)
    return output
