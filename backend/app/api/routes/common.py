from __future__ import annotations

from typing import Any


def ok(data: Any = None, **meta: Any) -> dict:
    return {"ok": True, "data": data, "meta": meta or None}
