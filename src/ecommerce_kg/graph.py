"""Load a validated dataset into a directed property graph."""

import json
import re
from collections import Counter
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Annotated, Literal

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schema import RELATIONSHIPS

NonEmpty = Annotated[str, Field(min_length=1, max_length=200)]
Money = Annotated[int, Field(ge=0)]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class NamedEntity(Record):
    id: NonEmpty
    name: NonEmpty


class LocatedEntity(NamedEntity):
    city: NonEmpty


class Product(NamedEntity):
    price_cents: Money
    keyword: NonEmpty | None = None
    brand_id: NonEmpty
    category_id: NonEmpty
    vendor_ids: Annotated[list[NonEmpty], Field(min_length=1)]


class OrderItem(Record):
    product_id: NonEmpty
    quantity: Annotated[int, Field(ge=1)]
    unit_price_cents: Money


class Order(Record):
    id: NonEmpty
    customer_id: NonEmpty
    vendor_id: NonEmpty
    placed_on: str
    status: Literal["pending", "shipped", "delivered", "cancelled"]
    items: Annotated[list[OrderItem], Field(min_length=1)]

    @model_validator(mode="after")
    def valid_date(self):
        if date.fromisoformat(self.placed_on).isoformat() != self.placed_on:
            raise ValueError("placed_on must be an ISO YYYY-MM-DD date")
        return self


class Dataset(Record):
    dataset_version: NonEmpty
    currency: Literal["USD"]
    brands: list[NamedEntity]
    categories: list[NamedEntity]
    vendors: list[LocatedEntity]
    products: list[Product]
    customers: list[LocatedEntity]
    orders: list[Order]


def word_occurrences(graph: nx.DiGraph, word: str) -> int:
    """Count whole-word occurrences in scalar graph, node and edge attribute values."""
    pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)

    def count(value):
        if isinstance(value, str):
            return len(pattern.findall(value))
        if isinstance(value, dict):
            return sum(count(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return sum(count(item) for item in value)
        return 0

    return (
        count(graph.graph)
        + sum(count(attrs) for _, attrs in graph.nodes(data=True))
        + sum(count(attrs) for _, _, attrs in graph.edges(data=True))
    )


def load_graph(dataset_path: str | Path | None = None) -> nx.DiGraph:
    path = Path(dataset_path) if dataset_path else files("ecommerce_kg").joinpath(
        "data/ecommerce.json"
    )
    dataset = Dataset.model_validate_json(path.read_text(encoding="utf-8"))
    graph = nx.DiGraph(dataset_version=dataset.dataset_version, currency=dataset.currency)

    def add_node(identifier, kind, **attrs):
        if identifier in graph:
            raise ValueError(f"Duplicate entity ID: {identifier}")
        graph.add_node(identifier, id=identifier, kind=kind, **attrs)

    for kind, records in (
        ("Brand", dataset.brands), ("Category", dataset.categories),
        ("Vendor", dataset.vendors), ("Customer", dataset.customers),
    ):
        for record in records:
            attrs = record.model_dump(exclude={"id"})
            add_node(record.id, kind, **attrs)
    for product in dataset.products:
        attrs = product.model_dump(include={"name", "price_cents", "keyword"}, exclude_none=True)
        add_node(product.id, "Product", currency=dataset.currency, **attrs)
    for order in dataset.orders:
        total = sum(item.quantity * item.unit_price_cents for item in order.items)
        add_node(
            order.id, "Order", placed_on=order.placed_on,
            status=order.status, total_cents=total, currency=dataset.currency,
        )

    def add_edge(source, target, relationship, **attrs):
        if source not in graph or target not in graph:
            raise ValueError(f"Dangling reference: {source} -> {target}")
        kinds = (graph.nodes[source]["kind"], graph.nodes[target]["kind"])
        if kinds != RELATIONSHIPS[relationship]:
            raise ValueError(f"Invalid endpoint types for {relationship}: {kinds}")
        if graph.has_edge(source, target):
            raise ValueError(f"Duplicate relationship: {source} -> {target}")
        graph.add_edge(source, target, relationship=relationship, **attrs)

    for product in dataset.products:
        add_edge(product.id, product.brand_id, "OF_BRAND")
        add_edge(product.id, product.category_id, "IN_CATEGORY")
        for vendor_id in product.vendor_ids:
            add_edge(vendor_id, product.id, "SUPPLIES")
    for order in dataset.orders:
        add_edge(order.customer_id, order.id, "PLACED")
        add_edge(order.id, order.vendor_id, "FULFILLED_BY")
        for item in order.items:
            if not graph.has_edge(order.vendor_id, item.product_id):
                raise ValueError(f"Order {order.id}: vendor does not supply {item.product_id}")
            add_edge(
                order.id, item.product_id, "CONTAINS", quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                line_total_cents=item.quantity * item.unit_price_cents,
            )
    occurrences = word_occurrences(graph, "banana")
    if occurrences != 5:
        raise ValueError(f"Expected exactly 5 banana values in graph, found {occurrences}")
    return nx.freeze(graph)


def graph_stats(graph: nx.DiGraph) -> dict:
    return {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "entities": dict(sorted(Counter(nx.get_node_attributes(graph, "kind").values()).items())),
        "relationships": dict(sorted(Counter(
            nx.get_edge_attributes(graph, "relationship").values()
        ).items())),
        "banana_occurrences": word_occurrences(graph, "banana"),
    }


def export_graph(graph: nx.DiGraph, destination: str | Path) -> None:
    """Export graph data, preserving node/edge properties for external inspection."""
    Path(destination).write_text(
        json.dumps(nx.node_link_data(graph, edges="edges"), indent=2) + "\n",
        encoding="utf-8",
    )
