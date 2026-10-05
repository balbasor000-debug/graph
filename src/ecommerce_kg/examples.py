"""Reproducible sample questions and their read-only query plans for offline demos."""

from .query import QueryPlan


def node(alias, kind):
    return {"alias": alias, "kind": kind}


def edge(alias, source, relationship, target):
    return {"alias": alias, "source": source, "relationship": relationship, "target": target}


def eq(alias, field, value):
    return {"alias": alias, "field": field, "op": "eq", "value": value}


def fields(*columns):
    return [{"alias": column.split(".")[0], "field": column.split(".")[1]} for column in columns]


def plan(nodes, edges=None, filters=None, select=None, aggregate=None):
    return QueryPlan.model_validate({
        "nodes": nodes,
        "edges": edges or [],
        "filters": filters or [],
        "select": fields(*(select or [])),
        "aggregate": aggregate,
        "order_by": fields(select[0]) if select else [],
    })


PRODUCT_BRAND_VENDOR = [node("p", "Product"), node("b", "Brand"), node("v", "Vendor")]
BRAND_VENDOR_EDGES = [edge("pb", "p", "OF_BRAND", "b"), edge("vp", "v", "SUPPLIES", "p")]

SAMPLE_QUERIES = {
    "Which products from Brand X are supplied by Vendor Y?": plan(
        PRODUCT_BRAND_VENDOR, BRAND_VENDOR_EDGES,
        [eq("b", "name", "Brand X"), eq("v", "name", "Vendor Y")],
        ["p.id", "p.name", "p.price_cents"],
    ),
    "Which products contain the keyword banana?": plan(
        [node("p", "Product")], filters=[eq("p", "keyword", "banana")],
        select=["p.id", "p.name", "p.keyword"],
    ),
    "How many products contain the keyword banana?": plan(
        [node("p", "Product")], filters=[eq("p", "keyword", "banana")],
        aggregate={"op": "count", "alias": "p"},
    ),
    "Which products did Alice Johnson order?": plan(
        [node("c", "Customer"), node("o", "Order"), node("p", "Product")],
        [edge("co", "c", "PLACED", "o"), edge("op", "o", "CONTAINS", "p")],
        [eq("c", "name", "Alice Johnson")], ["p.id", "p.name"],
    ),
    "Which customers have delivered orders containing products with the keyword banana?": plan(
        [node("c", "Customer"), node("o", "Order"), node("p", "Product")],
        [edge("co", "c", "PLACED", "o"), edge("op", "o", "CONTAINS", "p")],
        [eq("o", "status", "delivered"), eq("p", "keyword", "banana")],
        ["c.id", "c.name"],
    ),
    "What is the total value of delivered orders?": plan(
        [node("o", "Order")], filters=[eq("o", "status", "delivered")],
        aggregate={"op": "sum", "alias": "o", "field": "total_cents"},
    ),
    "Which vendors supply Wireless Headphones?": plan(
        [node("v", "Vendor"), node("p", "Product")],
        [edge("vp", "v", "SUPPLIES", "p")], [eq("p", "name", "Wireless Headphones")],
        ["v.id", "v.name"],
    ),
    "What products are in Electronics and cost less than $50?": plan(
        [node("p", "Product"), node("cat", "Category")],
        [edge("pc", "p", "IN_CATEGORY", "cat")],
        [eq("cat", "name", "Electronics"),
         {"alias": "p", "field": "price_cents", "op": "lt", "value": 5000}],
        ["p.id", "p.name", "p.price_cents"],
    ),
    "What items are in order O001, with quantities and line totals?": plan(
        [node("o", "Order"), node("p", "Product")],
        [edge("item", "o", "CONTAINS", "p")], [eq("o", "id", "O001")],
        ["p.id", "p.name", "item.quantity", "item.line_total_cents"],
    ),
    "Which products from Brand X are supplied by Orchard Supply?": plan(
        PRODUCT_BRAND_VENDOR, BRAND_VENDOR_EDGES,
        [eq("b", "name", "Brand X"), eq("v", "name", "Orchard Supply")],
        ["p.id", "p.name"],
    ),
}
