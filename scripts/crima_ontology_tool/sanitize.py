import re
import unicodedata
from html import unescape
from typing import TypeVar

import click
from rdflib import RDF, RDFS, Graph, Literal, Node, URIRef
from rdflib.namespace import split_uri

from crima_ontology_tool.util import create_graph, rdf_read, rdf_write


@click.command(name="sanitize")
@click.argument("input_files", metavar="INPUT_FILE...", nargs=-1)
@click.option("-o", "--output-file", default=".ttl:-", help="output text file ('-' for stdout, the default)")
@click.option("-p", "--prefixes-from", help="optionally reuse prefixes from supplied file")
def cli_sanitize(input_files: list[str], output_file: str = ".ttl:-", prefixes_from: str | None = None) -> None:
    """
    Sanitize RDF data from one or more files, writing sanitized RDF output to a specified file.

    File option/arguments allow the use of '-' to denote stdin/stdout, and an optional prefix '.ext:' to force a
    specific RDF format (e.g., '.ttl:path_to_rdf_file). Read from stdin if no input file is specified.
    """
    graph = create_graph()
    for input_file in input_files or [".ttl:-"]:
        rdf_read(graph, input_file)

    if prefixes_from:
        graph.namespace_manager.reset()
        rdf_read(graph, prefixes_from)

    graph = _sanitize(graph)

    builtin_datatype_namespaces = {
        "http://www.w3.org/2001/XMLSchema#",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "http://www.w3.org/2000/01/rdf-schema#",
        "http://www.w3.org/2002/07/owl#",
    }

    for s in list(graph.subjects(RDF.type, RDFS.Datatype)):
        if isinstance(s, URIRef):
            ns = split_uri(s)[0]
            if ns in builtin_datatype_namespaces:
                graph.remove((s, RDF.type, RDFS.Datatype))

    rdf_write(graph, output_file)


T = TypeVar("T")


def _sanitize[T](data: T) -> T:

    if isinstance(data, Graph):
        graph = create_graph(namespaces_from=data)
        for s, p, o in data:
            graph.add((_sanitize(s), _sanitize(p), _sanitize(o)))
        return graph

    if isinstance(data, URIRef):
        iri = _sanitize(str(data))
        return URIRef(iri)

    if isinstance(data, Literal):
        value = _sanitize(str(data))
        return Literal(value, lang=data.language, datatype=data.datatype)

    if isinstance(data, str) and not isinstance(data, Node):
        text = unicodedata.normalize("NFKC", data)
        text = _SANITIZE_CONTROL_CHARS_REGEX.sub("", data)
        text = text.translate(_SANITIZE_TRANSLATION_TABLE)
        return unescape(text)

    return data


_SANITIZE_CONTROL_CHARS_REGEX = re.compile(r"[\u202D\u200e]+")


_SANITIZE_TRANSLATION_TABLE = str.maketrans(
    {
        "\r": "",
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u2013": "-",
        "—": "-",
        "\u2212": "-",
        "\u00a0": " ",
        "\ufffc": " ",
    }
)
