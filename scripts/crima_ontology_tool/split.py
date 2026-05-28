from collections import defaultdict
from collections.abc import Generator
from dataclasses import dataclass, field
from itertools import chain
from pathlib import Path

import click
from rdflib import OWL, RDF, RDFS, BNode, Graph, IdentifiedNode, Node, URIRef
from rdflib.collection import Collection

from crima_ontology_tool.util import (
    EMPTY_SET,
    MOD,
    SWRL,
    VOAF,
    Triple,
    create_graph,
    get_namespace,
    rdf_read,
    rdf_write,
)


@click.command(name="split")
@click.argument("inputs", metavar="INPUT_FILE...", nargs=-1)
@click.option("-o", "--output-dir", default="./", help="directory where to create output files (default: working dir)")
@click.option("-l", "--leftover-file", help="RDF file where to save leftover triples (optional)")
def cli_split(inputs: list[str], output_dir: str = "./", leftover_file: str | None = None) -> None:
    """
    Split merged RDF data about multiple ontologies into separate output RDF files, one per ontology.

    Input data is read from specified input files (use '-' for stdin, prepend '.ext:' to force a different RDF format).
    Look for owl:Ontology IRIs in the input, read their annotations, and based on them emits a file for each ontology.
    (This utility was used to modularize the ontology, starting from a single file version.)
    """
    graph = create_graph()
    for input in inputs or [".ttl:-"]:
        rdf_read(graph, input)

    leftover = create_graph(namespaces_from=graph) if leftover_file else None

    modules = _extract_modules(graph)
    terms = _extract_terms(graph, modules)
    module_graphs = _allocate_triples(graph, modules, terms, leftover)

    for path_rel, graph_out in module_graphs.items():
        path_abs = Path(output_dir) / Path(path_rel)
        path_abs.parent.mkdir(parents=True, exist_ok=True)
        rdf_write(graph_out, str(path_abs))

    if leftover is not None:
        rdf_write(leftover, leftover_file)


@dataclass(frozen=True)
class Module:
    iri: URIRef
    serialization: str = field(compare=False)
    defines_namespaces_tbox: set[str] = field(compare=False)
    defines_namespaces_abox: set[str] = field(compare=False)
    includes_subjects_of: set[URIRef] = field(compare=False)
    includes_objects_of: set[URIRef] = field(compare=False)
    includes_statements_with: set[set[URIRef]] = field(compare=False)
    uses: set[URIRef] = field(compare=False)


@dataclass(frozen=True)
class IRITerm:
    iri: URIRef
    defined_by: set[Module]
    included_by: set[Module]


def _extract_modules(graph: Graph) -> dict[URIRef, Module]:

    iris: set[URIRef] = set(graph.subjects(RDF.type, OWL.Ontology))
    if any(not isinstance(n, URIRef) for n in iris):
        msg = f"Expected IRI as module identifier, got a BNode: check subjects of {MOD.hasSerialization}"
        raise ValueError(msg)

    return {
        iri: Module(
            iri=iri,
            serialization=graph.value(iri, MOD.hasSerialization),
            defines_namespaces_tbox={
                str(o) for p in (MOD.definesNamespace, MOD.definesNamespaceTBox) for o in graph.objects(iri, p)
            },
            defines_namespaces_abox={
                str(o) for p in (MOD.definesNamespace, MOD.definesNamespaceABox) for o in graph.objects(iri, p)
            },
            includes_subjects_of={p for p in graph.objects(iri, MOD.includesSubjectsOf) if isinstance(p, URIRef)},
            includes_objects_of={p for p in graph.objects(iri, MOD.includesObjectsOf) if isinstance(p, URIRef)},
            includes_statements_with={
                frozenset(Collection(graph, o)) for o in graph.objects(iri, MOD.includesStatementsWith)
            },
            uses={o for o in graph.subjects(iri, VOAF.usedBy) if o in iris}
            | {o for p in _VOAF_RELIES_ON_PROPS for o in graph.objects(iri, p) if o in iris},
        )
        for iri in iris
    }


def _extract_terms(graph: Graph, modules: dict[URIRef, Module]) -> dict[URIRef, IRITerm]:  # noqa: C901, PLR0912

    tbox_terms = set(graph.predicates())
    for t in _TBOX_METACLASSES:
        tbox_terms.update(s for s in graph.subjects(RDF.type, t) if isinstance(s, URIRef))
    for p in (RDFS.subClassOf, RDFS.subPropertyOf, OWL.inverseOf):
        tbox_terms.update(s for s in graph.subjects(predicate=p) if isinstance(s, URIRef))
    for p in (RDFS.subClassOf, RDFS.subPropertyOf, OWL.inverseOf, OWL.allValuesFrom, OWL.someValuesFrom):
        tbox_terms.update(o for o in graph.objects(predicate=p) if isinstance(o, URIRef))

    module_index: dict[tuple[bool, str], set[Module]] = {}
    for isabox in (False, True):
        for m in modules.values():
            for ns in m.defines_namespaces_abox if isabox else m.defines_namespaces_tbox:
                module_index.setdefault((isabox, ns), set()).add(m)

    allocation: dict[URIRef, IRITerm] = {}

    for t in {t for triple in graph for t in triple if isinstance(t, URIRef)}:
        isabox = t not in tbox_terms
        ns = get_namespace(t) or str(t)
        if ns not in _IGNORED_NAMESPACES:
            defined_by = frozenset(module_index.get((isabox, ns), EMPTY_SET))
            allocation[t] = IRITerm(iri=t, defined_by=defined_by, included_by=defined_by)

    for s, o in chain(
        ((s, o) for s, _, o in graph.triples((None, RDFS.isDefinedBy, None))),
        ((o, s) for s, _, o in graph.triples((None, MOD.definesTerm, None))),
    ):
        m = modules.get(o)
        term = allocation.get(s)
        if m and term and m not in term.defined_by:
            defined_by = frozenset({m, *term.defined_by})
            allocation[s] = IRITerm(iri=s, defined_by=defined_by, included_by=defined_by)

    # Assign Ontology IRIs exclusively to themselves, overriding prior allocations
    for m in modules.values():
        defined_by = frozenset({m})
        allocation[m.iri] = IRITerm(iri=m.iri, defined_by=defined_by, included_by=defined_by)

    for m in modules.values():
        pairs = {
            (s, o)
            for p in m.includes_objects_of
            for s, _, o in graph.triples((None, p, None))
            if isinstance(o, IdentifiedNode)
        } | {
            (s, o)
            for p in m.includes_subjects_of
            for o, _, s in graph.triples((None, p, None))
            if isinstance(s, IdentifiedNode)
        }
        bnodes: set[BNode] = set()
        fixpoint = False
        while not fixpoint:
            fixpoint = True
            for s, o in pairs:
                s_term = allocation.get(s)
                if (s_term and m in s_term.included_by) or s in bnodes:
                    if isinstance(o, BNode):
                        if o not in bnodes:
                            bnodes.add(o)
                            fixpoint = False
                    else:
                        o_term = allocation.get(o)
                        if o_term and m not in o_term.included_by:
                            included_by = frozenset({m, *o_term.included_by})
                            allocation[o] = IRITerm(iri=o, defined_by=o_term.defined_by, included_by=included_by)
                            fixpoint = False

    return allocation


def _chunk_triples(graph: Graph) -> Generator[list[Triple]]:  # noqa: C901
    """
    Split an RDF graph into minimal chunks so that all triples for a BNode are in the same chunk.

    The rationale is that BNodes have local scope and their triples cannot be split across files, hence they must be
    allocated to the same Ontology file. If there are no BNodes, returned chunks consist just of one triple.

    :param graph: the RDF graph whose triples have to be chunked
    :return: a generator that returns chunks as they are identified, each chunk being a non-empty list of triples
    """
    # Allocate a set to track BNodes visited so far, as they cannot be returned in following chunks
    visited_bnodes = set()

    # Recursive helper function that fetches all triples of BNode and of all other BNodes linked to it, adding these
    # triples to the passed 'chunk' list. Return False (with no triple added) if BNode was already visited.
    def visit(node: BNode, chunk: list[Triple]) -> bool:
        if node in visited_bnodes:
            return False
        visited_bnodes.add(node)
        for _, p, o in graph.triples((node, None, None)):
            if not isinstance(o, BNode) or not visit(o, chunk):
                chunk.append((node, p, o))
        for s, p, _ in graph.triples((None, None, node)):
            if not isinstance(s, BNode) or not visit(s, chunk):
                chunk.append((s, p, node))
        return True

    # Scans the graph one triple at a time, visiting encountered BNodes, and returning all non empty chunks
    for s, p, o in graph:
        chunk = []
        if isinstance(s, BNode):
            visit(s, chunk)
        elif isinstance(o, BNode):
            visit(o, chunk)
        else:
            chunk.append((s, p, o))
        if len(chunk) > 0:
            yield chunk


def _allocate_triples(  # noqa: C901, PLR0912
    graph: Graph, modules: dict[URIRef, Module], terms: dict[URIRef, IRITerm], leftover: Graph | None = None
) -> dict[str, Graph]:

    postponed_chunks: dict[Node, list[Triple]] = {}

    def postpone(chunk: list[Triple]) -> bool:
        if len(chunk) == 1:
            s, p, o = chunk[0]
            if p == RDF.type and o == SWRL.Variable:
                postponed_chunks[s] = chunk
                return True
        return False

    module_deps = {m: {modules[u] for u in m.uses} for m in modules.values()}

    module_stmt_iris_idx: dict[URIRef, set[Module]] = defaultdict(set)
    for m in modules.values():
        for stmt_iris in m.includes_statements_with:
            for iri in stmt_iris:
                module_stmt_iris_idx[iri].add(m)

    module_graphs = {m.serialization: create_graph(namespaces_from=graph) for m in modules.values() if m.serialization}

    for chunk in _chunk_triples(graph):
        emitted = False

        chunk_terms_iris = {t for triple in chunk for t in triple if isinstance(t, URIRef)}
        chunk_terms = {terms[iri] for iri in chunk_terms_iris if iri in terms}

        candidate_modules_base: set[Module] = {
            m
            for s, p, o in chunk
            for t in ((s, o) if p != RDF.type else (s,))
            for m in (terms[t].included_by if t in terms else EMPTY_SET)
            if m.serialization
        }

        candidate_modules_extra: set[Module] = {
            m for iri in chunk_terms_iris for m in module_stmt_iris_idx.get(iri, EMPTY_SET)
        }

        candidate_modules = candidate_modules_base | candidate_modules_extra

        for m in candidate_modules:
            m_deps = module_deps[m]
            emit_to_m = m in candidate_modules_base and all(
                m in t.included_by or not m_deps.isdisjoint(t.defined_by) for t in chunk_terms
            )

            if not emit_to_m:
                for stmt_iris in m.includes_statements_with:
                    if stmt_iris.issubset(chunk_terms_iris) and all(
                        m in t.included_by or not m_deps.isdisjoint(t.defined_by)
                        for t in chunk_terms
                        if t.iri not in stmt_iris
                    ):
                        emit_to_m = True
                        continue

            if emit_to_m:
                emitted = True
                mg = module_graphs[m.serialization]
                for triple in chunk:
                    mg.add(triple)

        if not emitted and not postpone(chunk) and leftover is not None:
            for triple in chunk:
                leftover.add(triple)

    if postponed_chunks:
        module_nodes = {k: {n for triple in g for n in triple} for k, g in module_graphs.items()}
        for node, chunk in postponed_chunks.items():
            emitted = False
            for k, nodes in module_nodes.items():
                if node in nodes:
                    emitted = True
                    g = module_graphs[k]
                    for triple in chunk:
                        g.add(triple)
            if not emitted and leftover is not None:
                for triple in chunk:
                    leftover.add(triple)

    return module_graphs


_IGNORED_NAMESPACES = {
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://www.w3.org/2000/01/rdf-schema#",
    "http://www.w3.org/2002/07/owl#",
    "http://www.w3.org/2001/XMLSchema#",
    "http://www.w3.org/2003/11/swrl#",
    "urn:swrl:var#",
}


_VOAF_RELIES_ON_PROPS = {
    VOAF.reliesOn,
    VOAF.extends,
    VOAF.metadataVoc,
    VOAF.specializes,
    VOAF.generalizes,
    VOAF.hasEquivalencesWith,
    VOAF.hasDisjunctionsWith,
}


_TBOX_METACLASSES = {
    RDF.Property,
    OWL.DatatypeProperty,
    OWL.ObjectProperty,
    OWL.AnnotationProperty,
    OWL.FunctionalProperty,
    OWL.SymmetricProperty,
    OWL.AsymmetricProperty,
    OWL.ReflexiveProperty,
    OWL.IrreflexiveProperty,
    OWL.TransitiveProperty,
    RDFS.Class,
    OWL.Class,
    RDFS.Datatype,
    OWL.Restriction,
    OWL.Ontology,
}
