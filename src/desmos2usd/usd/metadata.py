from __future__ import annotations

import json
import re

from desmos2usd.parse.classify import ClassifiedExpression


def usd_string(value: object) -> str:
    return json.dumps("" if value is None else str(value), ensure_ascii=True)


def usd_identifier(value: str) -> str:
    identifier = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not identifier or identifier[0].isdigit():
        identifier = f"_{identifier}"
    return identifier


def prim_name(item: ClassifiedExpression) -> str:
    expr_id = usd_identifier(item.ir.expr_id)
    return usd_identifier(f"expr_{item.ir.order:04d}_{expr_id}")


def custom_metadata_lines(item: ClassifiedExpression) -> list[str]:
    source = item.ir.source
    return [
        f"custom string desmos:url = {usd_string(source.url)}",
        f"custom string desmos:hash = {usd_string(source.graph_hash)}",
        f"custom string desmos:exprId = {usd_string(item.ir.expr_id)}",
        f"custom int desmos:order = {item.ir.order}",
        f"custom string desmos:latex = {usd_string(item.ir.latex)}",
        f"custom string desmos:constraints = {usd_string(item.metadata_constraints)}",
        f"custom string desmos:kind = {usd_string(item.kind)}",
        f"custom string desmos:color = {usd_string(item.ir.color or '')}",
        f"custom bool desmos:hidden = {str(bool(item.ir.hidden)).lower()}",
    ]

