import logging
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

import click
from rdflib import OWL, RDF, URIRef
from rdflib.util import guess_format

from crima_vkg_tool.util import create_graph

_LOGGER = logging.getLogger(__name__)


@click.command(name="catalog")
@click.argument("inputs", metavar="INPUT_PATH...", nargs=-1)
@click.option(
    "-o",
    "--output-file",
    default="-",
    help="output catalog file (e.g., catalog-v001.xml, use '-' for stdout, the default)",
)
def cli_catalog(inputs: list[str], output_file: str = "-") -> None:
    """
    Generate catalog-v001.xml files for use in Protégé / OWL API.

    Scan the RDF/OWL files supplied looking for owl:Ontology declarations. Generate the XML content of a
    catalog-v001.xml file with one entry for each owl:Ontology found, pointing to the respective file.
    Identifiers (informational) in the catalog XML are generated based on file name, plus a counter in case
    multiple ontologies are detected in the same file.
    """
    paths = {Path(i) for i in inputs}
    dirs = {p for p in paths if p.is_dir()}
    files = {p for p in paths if p.is_file()} | {f for d in dirs for f in d.rglob("*") if guess_format(f.as_posix())}

    root = ET.Element("catalog", attrib={"prefer": "public", "xmlns": "urn:oasis:names:tc:entity:xmlns:xml:catalog"})

    for f in sorted(files):
        if str(f.parts[-1]) == "catalog-v001.xml":
            continue
        graph = create_graph()
        graph.parse(source=f)
        iris = {iri for iri, _, _ in graph.triples((None, RDF.type, OWL.Ontology)) if isinstance(iri, URIRef)}
        if not iris:
            _LOGGER.warning("File '%s' has no owl:Ontology declaration: ignoring file", f)
        elif len(iris) == 1:
            iri = next(iter(iris))
            id = f.as_posix().rsplit("/", 1)[-1].split(".", 1)[0]
            ET.SubElement(root, "uri", attrib={"id": id, "name": str(iri), "uri": f.as_posix()})
        else:
            _LOGGER.warning("File '%s' has multiple owl:Ontology declarations: generating multiple catalog entries", f)
            id_base = f.as_posix().rsplit("/", 1)[-1].split(".", 1)[0]
            for idx, iri in enumerate(sorted(iris)):
                id = f"{id_base}-{idx + 1}"
                ET.SubElement(root, "uri", attrib={"id": id, "name": str(iri), "uri": f.as_posix()})

    # Emit pretty-printed XML file (need to serialize, parse into DOM, serialize-again)
    with sys.stdout.buffer if output_file == "-" else Path(output_file).open("wb") as f:
        dom = minidom.parseString(ET.tostring(root, "utf-8", xml_declaration=True))  # noqa: S318
        f.write(dom.toprettyxml(indent="    ", encoding="utf-8"))
