"""Build deterministic CRS cross-reference graphs for parsed Colorado bills.

This module reads enriched parsed bill records, indexes their Colorado Revised
Statutes references, builds an undirected bill-to-bill graph using shared CRS
references as edges, and exports that graph in a machine-readable JSON format.
It uses only deterministic local data and makes no network or LLM calls.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

try:
    import networkx as nx
    from networkx.readwrite import json_graph
except ModuleNotFoundError as exc:
    nx = None
    json_graph = None
    NETWORKX_IMPORT_ERROR = exc
else:
    NETWORKX_IMPORT_ERROR = None

DEFAULT_INPUT_DIR = "data/structured_output"
DEFAULT_OUTPUT_PATH = "data/structured_output/bill_graph.json"

LOGGER = logging.getLogger(__name__)


def load_all_bills(input_dir: str = DEFAULT_INPUT_DIR) -> list[dict]:
    """Load every parsed bill record from a structured-output directory.

    Args:
        input_dir: Directory containing ``*_parsed.json`` files.

    Returns:
        A list of bill dictionaries. Files that cannot be read as JSON objects
        are skipped and logged.
    """
    bills: list[dict] = []
    directory = Path(input_dir)

    for bill_path in sorted(directory.glob("*_parsed.json")):
        try:
            with bill_path.open("r", encoding="utf-8") as file_obj:
                bill = json.load(file_obj)
            if not isinstance(bill, dict):
                raise ValueError("top-level JSON value is not an object")
            bills.append(bill)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            LOGGER.error("Failed to load bill file %s: %s", bill_path, exc)

    return bills


def build_crs_index(bills: list[dict]) -> dict[str, list[str]]:
    """Build a reverse index from CRS references to bill numbers.

    Args:
        bills: Parsed bill records.

    Returns:
        Mapping of normalized CRS reference strings to sorted bill-number lists.
    """
    index: dict[str, set[str]] = {}

    for bill in bills:
        bill_number = _bill_number(bill)
        if bill_number is None:
            continue

        for reference in _bill_crs_references(bill):
            index.setdefault(reference, set()).add(bill_number)

    return {
        reference: sorted(bill_numbers)
        for reference, bill_numbers in sorted(index.items())
    }


def build_bill_graph(bills: list[dict]) -> nx.Graph:
    """Build a bill relationship graph from shared CRS references.

    Args:
        bills: Parsed bill records.

    Returns:
        A NetworkX graph with bill-number nodes and weighted shared-reference
        edges.
    """
    networkx = _require_networkx()
    graph = networkx.Graph()

    for bill in bills:
        bill_number = _bill_number(bill)
        if bill_number is None:
            continue
        graph.add_node(
            bill_number,
            title=str(bill.get("title", "")),
            sponsor_count=_sponsor_count(bill),
            section_count=_section_count(bill),
        )

    crs_index = build_crs_index(bills)
    for reference, bill_numbers in crs_index.items():
        for left_bill, right_bill in combinations(bill_numbers, 2):
            if graph.has_edge(left_bill, right_bill):
                shared_refs = graph[left_bill][right_bill]["_shared_refs"]
                shared_refs.add(reference)
            else:
                graph.add_edge(left_bill, right_bill, _shared_refs={reference})

    for left_bill, right_bill, data in graph.edges(data=True):
        shared_refs = sorted(data.pop("_shared_refs", set()))
        data["shared_refs"] = shared_refs
        data["weight"] = len(shared_refs)

    return graph


def find_clusters(graph: nx.Graph) -> list[list[str]]:
    """Find bill clusters represented by connected components.

    Args:
        graph: Bill relationship graph.

    Returns:
        Components sorted by size from largest to smallest, with bill numbers
        sorted inside each component.
    """
    networkx = _require_networkx()
    clusters = [sorted(component) for component in networkx.connected_components(graph)]
    return sorted(clusters, key=lambda cluster: (-len(cluster), cluster))


def get_bill_neighbors(graph: nx.Graph, bill_number: str) -> list[dict]:
    """Return neighboring bills sorted by shared-reference weight.

    Args:
        graph: Bill relationship graph.
        bill_number: Bill number to query, such as ``HB25-1001``.

    Returns:
        Neighbor records containing bill number, shared CRS references, and
        edge weight. Missing bills return an empty list.
    """
    if bill_number not in graph:
        return []

    neighbors: list[dict] = []
    for neighbor in graph.neighbors(bill_number):
        edge_data = graph[bill_number][neighbor]
        shared_refs = list(edge_data.get("shared_refs", []))
        neighbors.append(
            {
                "bill_number": neighbor,
                "shared_refs": shared_refs,
                "weight": int(edge_data.get("weight", len(shared_refs))),
            }
        )

    return sorted(
        neighbors,
        key=lambda item: (-int(item["weight"]), str(item["bill_number"])),
    )


def export_graph(
    graph: nx.Graph, output_path: str = DEFAULT_OUTPUT_PATH
) -> str:
    """Export a bill graph in NetworkX node-link JSON format.

    Args:
        graph: Bill relationship graph.
        output_path: Destination JSON path.

    Returns:
        The written output path.
    """
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    node_link = _require_json_graph()
    payload = node_link.node_link_data(graph)

    with destination.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=2, ensure_ascii=False)
        file_obj.write("\n")

    return str(destination)


def build_and_export(input_dir: str = DEFAULT_INPUT_DIR) -> dict:
    """Build the CRS graph, export it, and return graph summary statistics.

    Args:
        input_dir: Directory containing ``*_parsed.json`` bill records.

    Returns:
        Summary dictionary with bill, edge, cluster, largest-cluster, and
        isolated-bill counts.
    """
    return _build_and_export(input_dir=input_dir, output_path=DEFAULT_OUTPUT_PATH)


def _build_and_export(
    input_dir: str = DEFAULT_INPUT_DIR,
    output_path: str = DEFAULT_OUTPUT_PATH,
) -> dict:
    """Build and export the graph to an explicit destination path."""
    bills = load_all_bills(input_dir)
    graph = build_bill_graph(bills)
    clusters = find_clusters(graph)
    export_graph(graph, output_path)

    return {
        "total_bills": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
        "clusters": len(clusters),
        "largest_cluster_size": len(clusters[0]) if clusters else 0,
        "isolated_bills": sum(
            1 for node in graph.nodes if graph.degree(node) == 0
        ),
    }


def _bill_number(bill: dict[str, Any]) -> str | None:
    """Return a non-empty bill number from a bill record, if present."""
    bill_number = bill.get("bill_number")
    if isinstance(bill_number, str) and bill_number.strip():
        return bill_number.strip()
    return None


def _bill_crs_references(bill: dict[str, Any]) -> list[str]:
    """Return de-duplicated CRS references for a bill."""
    references = bill.get("crs_references")
    if not isinstance(references, list):
        return []

    seen: set[str] = set()
    cleaned: list[str] = []
    for reference in references:
        if not isinstance(reference, str):
            continue
        normalized = reference.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            cleaned.append(normalized)
    return cleaned


def _sponsor_count(bill: dict[str, Any]) -> int:
    """Count House and Senate sponsors on a bill record."""
    sponsors = bill.get("sponsors")
    if not isinstance(sponsors, dict):
        return 0

    total = 0
    for key in ("house_sponsors", "senate_sponsors"):
        values = sponsors.get(key)
        if isinstance(values, list):
            total += sum(1 for value in values if isinstance(value, str))
    return total


def _section_count(bill: dict[str, Any]) -> int:
    """Count parsed sections on a bill record."""
    sections = bill.get("sections")
    return len(sections) if isinstance(sections, list) else 0


def _require_networkx() -> Any:
    """Return the NetworkX module or raise a clear dependency error."""
    if nx is None:
        raise RuntimeError(
            "networkx is required for graph building. Install dependencies with "
            "pip install -r requirements.txt."
        ) from NETWORKX_IMPORT_ERROR
    return nx


def _require_json_graph() -> Any:
    """Return NetworkX's JSON graph helper or raise a dependency error."""
    if json_graph is None:
        raise RuntimeError(
            "networkx is required for graph export. Install dependencies with "
            "pip install -r requirements.txt."
        ) from NETWORKX_IMPORT_ERROR
    return json_graph


def _print_json(payload: Any) -> None:
    """Print a JSON payload to stdout."""
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Build CRS cross-reference graphs from parsed bill records."
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        help=f"Directory of *_parsed.json files. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help=f"Graph JSON output path. Default: {DEFAULT_OUTPUT_PATH}",
    )
    parser.add_argument(
        "--query",
        help="Optional bill number to inspect for graph neighbors.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the graph-builder CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = _build_parser().parse_args(argv)

    bills = load_all_bills(args.input_dir)
    graph = build_bill_graph(bills)

    if args.query:
        bill_number = args.query.strip().upper()
        if bill_number not in graph:
            print(f"Bill not found in graph: {bill_number}", file=sys.stderr)
            _print_json([])
            return 1
        _print_json(get_bill_neighbors(graph, bill_number))
        return 0

    export_graph(graph, args.output)
    clusters = find_clusters(graph)
    summary = {
        "total_bills": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
        "clusters": len(clusters),
        "largest_cluster_size": len(clusters[0]) if clusters else 0,
        "isolated_bills": sum(1 for node in graph.nodes if graph.degree(node) == 0),
    }
    _print_json(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
