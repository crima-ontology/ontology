import builtins
import contextlib
import gzip
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

from rdflib import Dataset, Graph, Namespace, Node, URIRef
from rdflib.namespace import split_uri
from rdflib.util import guess_format

type Triple = tuple[Node, Node, Node]


try:
    from rdfcanon import RDFCanon, RDFCanonTimeTicker

    HAS_RDFCANON = True
except ImportError:
    HAS_RDFCANON = False


EMPTY_SET = frozenset()

BIBO = Namespace("http://purl.org/ontology/bibo/")
PROV = Namespace("http://www.w3.org/ns/prov#")
SWRL = Namespace("http://www.w3.org/2003/11/swrl#")
VOAF = Namespace("http://purl.org/vocommons/voaf#")
MOD = Namespace("mod:")


def create_graph(*, namespaces_from: Graph | None = None) -> Graph:
    """
    Create an RDF graph, optionally copying <prefix, namespace> bindings from a supplied graph.

    :param namespaces_from: the optional graph to copy <prefix, namespace> bindings from
    :return the created RDF graph
    """
    graph = Graph(bind_namespaces="core")
    if namespaces_from is not None:
        for prefix, namespace in namespaces_from.namespaces():
            graph.bind(prefix, namespace)
    return graph


def replace_terms(graph: Graph, replacements: dict[Node, Node], positions: set[int] = frozenset({0, 1, 2})) -> None:
    to_add = []
    to_remove = []

    for triple in graph:
        if any(triple[i] in replacements for i in positions):
            to_remove.append(triple)
            new_triple = tuple(
                replacements.get(triple[i], triple[i]) if i in positions else triple[i] for i in range(3)
            )
            if None not in new_triple:
                to_add.append(new_triple)

    for triple in to_remove:
        graph.remove(triple)

    for triple in to_add:
        graph.add(triple)


def rdf_read(graph: Graph, path: str) -> None:
    """
    Read the RDF file at the path specified ('-' for stdin, '.ext:' prefix to override format) into a RDF graph.

    :param graph: the RDF graph where to add parsed triples and <prefix, namespace> bindings
    :param path: the file path or '-' for stdin, optionally prepended with '.ext:' to override detected RDF format
    """
    tokens = path.split(":")
    path = tokens[-1]
    if path.endswith((".xml", ".xml.gz")) and len(tokens) == 1:
        msg = "Refusing to parse .xml files: use .rdf extension, or force RDF/XML parsing via .xml: prefix"
        raise ValueError(msg)
    fmt = guess_format(path if len(tokens) == 1 else "dummy" + tokens[0])
    with (
        sys.stdin.buffer if path == "-" else gzip.open(path, "rb") if path.endswith(".gz") else Path.open(path, "rb")
    ) as f:
        graph.parse(source=f, format=fmt)


def rdf_write(graph: Graph, path: str, *, canonicalize_ntriples: bool = True) -> None:
    """
    Write an RDF graph to the file at the path specified ('-' for stdout, '.ext:' prefix to override format).

    In case of NTriples, the serialized is canonicalized via RDFC-1.0, so that BNodes are assigned consistent IDs.

    :param graph: the RDF graph whose triples and <prefix, namespace> bindings are to be written to file
    :param path: the file path or '-' for stdout, optionally prepended with '.ext:' to override detected RDF format
    """
    tokens = path.split(":")
    path = tokens[-1]
    fmt = guess_format(path if len(tokens) == 1 else "dummy" + tokens[0])
    if HAS_RDFCANON and canonicalize_ntriples and fmt in ("nt", "ntriples"):
        dataset = Dataset()
        for triple in graph:
            dataset.add(triple)
        canonizer = RDFCanon(hash_algorithm="sha256", dataset=dataset, ticker=RDFCanonTimeTicker(30000))
        with _suppress_print():
            serialized_ntriples = canonizer.canonize()
        with sys.stdout if path == "-" else gzip.open(path, "w") if path.endswith(".gz") else Path.open(path, "w") as f:
            f.write(serialized_ntriples)
    else:
        with (
            sys.stdout.buffer
            if path == "-"
            else gzip.open(path, "wb")
            if path.endswith(".gz")
            else Path.open(path, "wb") as f
        ):
            graph.serialize(destination=f, format=fmt, canon=True)


def get_namespace(iri: URIRef) -> str | None:
    try:
        return split_uri(iri)[0]
    except ValueError:
        return None


@contextlib.contextmanager
def _suppress_print() -> Generator[Any]:
    original_print = builtins.print
    builtins.print = lambda *_, **__: None
    try:
        yield
    finally:
        builtins.print = original_print
