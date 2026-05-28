import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from textwrap import dedent

import click
from rdflib import OWL, Graph, URIRef

from crima_vkg_tool.util import MOD, VOAF, create_graph, rdf_read


@click.command(name="mermaid")
@click.argument("inputs", metavar="INPUT_FILE...", nargs=-1)
@click.option("-o", "--output-file", default="-", help="output markdown file ('-' for stdout, the default)")
@click.option("--voaf", is_flag=True, help="use voaf:reliesOn instead of owl:imports to build the diagram")
@click.option(
    "-e", "--extra-content", multiple=True, help="optional additional Mermaid code to inject into the diagram"
)
def cli_mermaid(
    inputs: list[str], output_file: str = "-", voaf: bool = False, extra_content: tuple[str, ...] = ()
) -> None:  # noqa: FBT001, FBT002
    """
    Generate a Markdown + Mermaid diagram of ontology voaf:reliesOn relations.

    Identifies owl:Ontologies with mod:hasSerialization metadata in specified RDF/OWL files, which becomes nodes of a
    graph having voaf:reliesOn relations edges. The graph is encoded as a Mermaid flowchart, with nodes grouped by the
    folder where they reside. Additional content (e.g., invisible edges to control layout) can be optionally injected
    before the generated list of edges (option -e).
    """
    graph = create_graph()
    for input in inputs or [".ttl:-"]:
        rdf_read(graph, input)

    nodes = _collect_nodes(graph)
    edges = _collect_edges(graph, voaf)
    diagram = _mermaid(nodes, edges, extra_content)

    with sys.stdout if output_file == "-" else Path(output_file).open("w") as f:
        f.write(diagram)


@dataclass(frozen=True)
class Subgraph:
    id: str
    label: str


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    iri: URIRef
    subgraph: Subgraph | None


def _collect_nodes(graph: Graph) -> dict[URIRef, Node]:

    nodes: dict[URIRef, Node] = {}
    for iri, _, serialization in graph.triples((None, MOD.hasSerialization, None)):
        if isinstance(iri, URIRef):
            parts = str(serialization).rsplit("/", 1)
            subgraph = (
                Subgraph("sg_main", " ")
                if len(parts) == 1
                else Subgraph(id="sg_" + re.sub(r"[^a-zA-Z]", "_", parts[0]), label=parts[0])
            )
            label = parts[-1].split(".", 1)[0]
            nodes[iri] = Node(id=re.sub(r"[^a-zA-Z]", "_", label), label=label, iri=iri, subgraph=subgraph)

    return nodes


def _collect_edges(graph: Graph, use_voaf: bool = False) -> dict[URIRef, set[URIRef]]:  # noqa: FBT002

    node_iris = {iri for iri, _, _ in graph.triples((None, MOD.hasSerialization, None)) if isinstance(iri, URIRef)}

    if use_voaf:
        props = (
            VOAF.reliesOn,
            VOAF.extends,
            VOAF.metadataVoc,
            VOAF.specializes,
            VOAF.generalizes,
            VOAF.hasEquivalencesWith,
            VOAF.hasDisjunctionsWith,
        )
    else:
        props = (OWL.imports,)

    edges = {iri: {o for p in props for o in graph.objects(iri, p) if o in node_iris and o != iri} for iri in node_iris}

    for n_parents in edges.values():
        n_parents.difference_update({p2 for p1 in n_parents for p2 in edges[p1]})

    return edges


def _mermaid(nodes: dict[URIRef, Node], edges: dict[URIRef, set[URIRef]], extra_content: Iterable[str] = ()) -> str:

    sorted_nodes = sorted(nodes.values(), key=lambda n: n.id)
    sorted_subgraphs = sorted({n.subgraph for n in nodes.values() if n.subgraph}, key=lambda s: s.id)

    buffer = StringIO()
    buffer.write(
        dedent("""\
        ```mermaid
        flowchart BT
            classDef invisible fill:transparent,stroke:transparent;
            classDef subvoc fill:#7588a3,stroke:#555555,stroke-width:1px;
            classDef voc fill:#7588a3,stroke:#555555,stroke-width:2px;\n""")
    )
    for s in sorted_subgraphs:
        buffer.write(f"    style {s.id} fill:transparent,stroke:#7588a3,stroke-width:3px;\n")
    buffer.write("\n")

    for s in sorted_subgraphs:
        buffer.write(f'    subgraph {s.id}["<b>{s.label}</b>"]\n')
        for n in (n for n in sorted_nodes if n.subgraph == s):
            buffer.write(f'        {n.id}["<b>{n.label}</b>"]:::subvoc\n')
        buffer.write("    end\n\n")

    if extra_content:
        for line in extra_content:
            buffer.write(f"    {line}\n")
        buffer.write("\n")

    for e in sorted([f"    {nodes[n].id} --> {nodes[p].id}\n" for n, n_parents in edges.items() for p in n_parents]):
        buffer.write(e)
    buffer.write("\n")

    for n in sorted_nodes:
        buffer.write(f'    click {n.id} href "{n.iri}"\n')

    buffer.write("```\n")

    return buffer.getvalue()
