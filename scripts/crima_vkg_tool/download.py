import logging
from pathlib import Path

import click
import requests
from rdflib import OWL, RDF, Graph, URIRef

from crima_vkg_tool.util import create_graph

_LOGGER = logging.getLogger(__name__)


@click.command(name="download")
@click.option(
    "-o",
    "--output-dir",
    default="./extvoc",
    metavar="DIR",
    help="directory where to download external vocabularies (default: './extvoc')",
)
def cli_download(output_dir: str = "./extvoc") -> None:
    """
    Download external vocabularies referenced by the CRIMA ontology into the directory specified.

    Vocabularies are downloaded in Turtle format, performing conversion to Turtle if necessary. For compatibility with
    Protégé, an additional triple '<vocabulary_iri> a owl:Ontology' is stored in case the downloaded vocabulary does
    not already contain it. A vocabulary is not downloaded if the corresponding file is already present in the target
    directory (delete it to force download). Parsing and serializing via rdflib is always performed even if data
    already comes in Turtle, to both handle relative IRIs (replaced as full IRIs in saved file) and provide a
    consistent output that facilitates finding differences.
    """
    # Create output directory (and parent dirs) if needed
    dir = Path(output_dir)
    dir.mkdir(parents=True, exist_ok=True)

    # Download all vocabularies
    # fmt: off
    _get(dir / "as.ttl", "https://www.w3.org/ns/activitystreams-owl")
    _get(dir / "bibo.ttl", "http://purl.org/ontology/bibo/")
    _get(dir / "cc.ttl", "https://creativecommons.org/schema.rdf", fmt="xml", iri="http://creativecommons.org/ns#")
    _get(dir / "clc.ttl", "http://www.w3.org/2015/03/corine", iri="http://www.w3.org/2015/03/corine")
    _get(dir / "dbo.ttl", "https://akswnc7.informatik.uni-leipzig.de/dstreitmatter/archivo/dbpedia.org/ontology--DEV/"
         "2024.07.29-001000/ontology--DEV_type=orig.owl", fmt="xml")
    _get(dir / "dcat.ttl", "https://www.w3.org/ns/dcat3.ttl")
    _get(dir / "dcmitype.ttl", "https://www.dublincore.org/specifications/dublin-core/dcmi-terms/dublin_core_type.ttl",
         iri="http://purl.org/dc/dcmitype/") # not imported
    _get(dir / "dcterms.ttl", "https://www.dublincore.org/specifications/dublin-core/dcmi-terms/dublin_core_terms.ttl",
         iri="http://purl.org/dc/terms/")
    _get(dir / "dpo.ttl", "https://raw.githubusercontent.com/KnowWhereGraph/dmdo/refs/heads/main/modules/"
         "disaster-properties-module/disaster-properties-ontology.ttl")
    _get(dir / "dtype.ttl", "https://www.linkedmodel.org/schema/dtype", fmt="xml")
    _get(dir / "foaf.ttl", "https://xmlns.com/foaf/spec/index.rdf", fmt="xml")
    _get(dir / "geo.ttl", "https://opengeospatial.github.io/ogc-geosparql/geosparql11/geo.ttl") # https://www.ogc.org/standards/geosparql/
    _get(dir / "org.ttl", "https://www.w3.org/ns/org")
    _get(dir / "prov.ttl", "https://www.w3.org/ns/prov-o")
    _get(dir / "qudt.ttl", "https://qudt.org/schema/qudt")
    _get(dir / "qudt-coords.ttl", "https://qudt.org/schema/coordinateSystems/")
    _get(dir / "qudt-datatype.ttl", "https://qudt.org/schema/datatype")
    _get(dir / "qudt-facade.ttl", "https://qudt.org/schema/facade/qudt")
    _get(dir / "qudt-prefix.ttl", "https://qudt.org/vocab/prefix")
    _get(dir / "qudt-qkdv.ttl", "https://qudt.org/vocab/dimensionvector")
    _get(dir / "qudt-quantitykind.ttl", "https://qudt.org/vocab/quantitykind")
    _get(dir / "qudt-soqk.ttl", "https://qudt.org/vocab/soqk")
    _get(dir / "qudt-sou.ttl", "http://qudt.org/vocab/sou")
    _get(dir / "qudt-unit.ttl", "https://qudt.org/vocab/unit/")
    _get(dir / "qudt-usertest.ttl", None, iri="http://qudt.org/collection/usertest")
    _get(dir / "schema.ttl", "https://schema.org/version/latest/schemaorg-current-http.ttl", iri="http://schema.org/")
    _get(dir / "skos.ttl", "https://www.w3.org/TR/skos-reference/skos.rdf", fmt="xml")
    _get(dir / "sosa.ttl", "https://raw.githubusercontent.com/w3c/sdw-sosa-ssn/refs/heads/gh-pages/ssn/rdf/"
         "ontology/core/sosa.ttl") # not imported
    _get(dir / "sosa-common.ttl", "https://raw.githubusercontent.com/w3c/sdw-sosa-ssn/refs/heads/gh-pages/ssn/rdf/"
         "ontology/core/sosa-common.ttl")
    _get(dir / "sosa-obs.ttl", "https://raw.githubusercontent.com/w3c/sdw-sosa-ssn/refs/heads/gh-pages/ssn/rdf/"
         "ontology/core/sosa-observation.ttl")
    _get(dir / "swrl.ttl", "https://www.w3.org/submissions/2004/SUBM-SWRL-20040521/swrl.rdf", fmt="xml",
         iri="http://www.w3.org/2003/11/swrl#") # not imported
    _get(dir / "time.ttl", "http://www.w3.org/2006/time")
    _get(dir / "vaem.ttl", "https://www.linkedmodel.org/schema/vaem", fmt="xml")
    _get(dir / "vann.ttl", "https://vocab.org/vann/vann-vocab-20100607.rdf", fmt="xml")
    _get(dir / "voaf.ttl", "https://raw.githubusercontent.com/pyvandenbussche/lov/refs/heads/master/vocommons/voaf/v2.3/"
         "voaf_v2.3.rdf", fmt="xml")
    _get(dir / "wmdr-unit.ttl", "https://codes.wmo.int/wmdr/unit?_format=ttl&_view=with_metadata&status=valid",
         iri=URIRef("http://codes.wmo.int/wmdr/unit/"))
    _get(dir / "xkos.ttl", "http://rdf-vocabulary.ddialliance.org/xkos.ttl")


def _get(file: str, url: str | None, *, fmt: str | None = None, iri: str | URIRef | None = None) -> None:
    """
    Download a vocabulary file if missing.

    Asks for 'text/turtle' unless 'fmt' is given, in which case conversion will occur from that format. If 'iri'
    is given, a corresponding triple '<iri> a owl:Ontology' will be added. Errors are logged and ignored (no file
    saved).
    """
    try:
        if file.is_file():
            return
        _LOGGER.info("Processing %s: %s", file, url)
        graph = create_graph()
        for prefix, ns in Graph(bind_namespaces="rdflib").namespaces():
            if prefix != "schema":  # we use the HTTP version of Schema.org
                graph.namespace_manager.bind(prefix, ns)
        if url:
            headers = {} if fmt else {"Accept": "text/turtle"}
            response = requests.get(url, allow_redirects=True, headers=headers, timeout=10)
            response.raise_for_status()
            graph.parse(source=response.content, format=fmt, publicID=url)
        if iri or not url:
            iri = iri if isinstance(iri, URIRef) else URIRef(iri)
            graph.add((iri, RDF.type, OWL.Ontology))
        with file.open("wb") as f:
            graph.serialize(destination=f, format="longturtle")
    except Exception:
        _LOGGER.exception("Could not fetch %s", url)
