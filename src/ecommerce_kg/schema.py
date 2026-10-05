"""The property/relationship allowlist shared by graph validation and query validation."""

from typing import Literal

EntityKind = Literal["Product", "Brand", "Category", "Vendor", "Order", "Customer"]
RelationshipKind = Literal[
    "OF_BRAND", "IN_CATEGORY", "SUPPLIES", "PLACED", "CONTAINS", "FULFILLED_BY"
]

NODE_FIELDS = {
    "Product": {"id": str, "name": str, "price_cents": int, "currency": str, "keyword": str},
    "Brand": {"id": str, "name": str},
    "Category": {"id": str, "name": str},
    "Vendor": {"id": str, "name": str, "city": str},
    "Order": {
        "id": str, "placed_on": str, "status": str, "total_cents": int, "currency": str,
    },
    "Customer": {"id": str, "name": str, "city": str},
}

RELATIONSHIPS = {
    "OF_BRAND": ("Product", "Brand"),
    "IN_CATEGORY": ("Product", "Category"),
    "SUPPLIES": ("Vendor", "Product"),
    "PLACED": ("Customer", "Order"),
    "CONTAINS": ("Order", "Product"),
    "FULFILLED_BY": ("Order", "Vendor"),
}

EDGE_FIELDS = {
    relation: (
        {"quantity": int, "unit_price_cents": int, "line_total_cents": int}
        if relation == "CONTAINS" else {}
    )
    for relation in RELATIONSHIPS
}


def schema_description() -> dict:
    return {
        "nodes": {
            kind: {field: datatype.__name__ for field, datatype in fields.items()}
            for kind, fields in NODE_FIELDS.items()
        },
        "relationships": {
            kind: {
                "source": ends[0], "target": ends[1],
                "properties": {
                    field: datatype.__name__ for field, datatype in EDGE_FIELDS[kind].items()
                },
            }
            for kind, ends in RELATIONSHIPS.items()
        },
    }
