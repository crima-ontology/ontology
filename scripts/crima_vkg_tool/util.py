import gzip
import sys
from pathlib import Path

from rdflib import Graph, Namespace, Node, URIRef
from rdflib.namespace import split_uri
from rdflib.util import guess_format

type Triple = tuple[Node, Node, Node]


EMPTY_SET = frozenset()

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


def rdf_write(graph: Graph, path: str) -> None:
    """
    Write an RDF graph to the file at the path specified ('-' for stdout, '.ext:' prefix to override format).

    :param graph: the RDF graph whose triples and <prefix, namespace> bindings are to be written to file
    :param path: the file path or '-' for stdout, optionally prepended with '.ext:' to override detected RDF format
    """
    tokens = path.split(":")
    path = tokens[-1]
    fmt = guess_format(path if len(tokens) == 1 else "dummy" + tokens[0])
    opts = {"encoding": "utf-8"} if fmt in ("nt", "ntriples") else {}
    with (
        sys.stdout.buffer if path == "-" else gzip.open(path, "wb") if path.endswith(".gz") else Path.open(path, "wb")
    ) as f:
        graph.serialize(destination=f, format=fmt, canon=True, **opts)


def get_namespace(iri: URIRef) -> str | None:
    try:
        return split_uri(iri)[0]
    except ValueError:
        return None
