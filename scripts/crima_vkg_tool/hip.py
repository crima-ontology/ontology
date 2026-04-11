import json
import logging
import re
from time import sleep
from urllib.parse import urljoin

import click
import extruct
import requests
from lxml import html
from rdflib import DCTERMS, OWL, RDF, SKOS, Graph, Literal, Namespace, URIRef

from crima_vkg_tool.util import BIBO, PROV, create_graph, get_namespace, rdf_read, rdf_write, replace_terms

_LOGGER = logging.getLogger(__name__)


ARTICLE = Namespace("http://ogp.me/ns/article#")
CLEX = Namespace("http://www.semanticweb.org/crima/crima-lexicon#")
HIP_SCHEMA = Namespace("https://undrr-hip.org/")
OG = Namespace("https://ogp.me/ns#")
XHV = Namespace("http://www.w3.org/1999/xhtml/vocab#")

SCHEME = URIRef("https://www.preventionweb.net/drr-glossary/HIP-classification-system")
WEBSITE = URIRef("https://www.preventionweb.net/drr-glossary/hips")


@click.group(name="hip")
def cli_hip() -> None:
    """Utilities related to HIP Abox data."""


@cli_hip.command(name="crawl")
@click.option("-o", "--output-file", metavar="FILE", default=".ttl:-", help="output RDF file (default '.ttl:-')")
@click.option(
    "-u",
    "--url",
    metavar="URL",
    default="https://www.preventionweb.net/drr-glossary/hips",
    help="URL to start crawling from",
)
def cli_hip_crawl(output_file: str = ".ttl:-", url: str = "https://www.preventionweb.net/drr-glossary/hips") -> None:
    """
    Crawl RDF data embedded in HIP 2025 web pages and writes collected RDF to file.

    JSON-LD and RDFa data embedded in web pages is collected starting from the page at the root URL (default:
    https://www.preventionweb.net/drr-glossary/hips), then navigating to linked pages for specific hazards. Collected
    RDF is saved to file. It's also possible to crawl data for an individual specific hazard page, such as the one at
    https://www.preventionweb.net/understanding-disaster-risk/terminology/hips/mh0801.
    """
    # Create a RDF graph, setting prefixes
    graph = create_graph()
    _bind_prefixes(graph)

    # Crawl RDF data
    _crawl(graph, url)

    # Serialize collected RDF data (to file or stdout)
    rdf_write(graph, output_file)


def _crawl(graph: Graph, url: str) -> None:
    # Fetch the page raw content
    _LOGGER.info("Crawling %s", url)
    content = requests.get(url, headers=_HEADERS, timeout=10).content

    # Extracts JSON-LD and RDFA data embedded in the page
    data = extruct.extract(content, base_url=url, syntaxes=["json-ld", "rdfa"])
    for data_block in data.values():
        json_block = json.dumps(data_block, indent=4)
        graph.parse(data=json_block, format="json-ld", publicID=url)

    # Collect links to specific hazard pages
    tree = html.document_fromstring(content)
    specific_hazard_urls = {
        urljoin(url, u)
        for u in list(tree.xpath(".//table/tbody/tr//a/@href"))
        if re.search(r"/[a-zA-Z]{2}[0-9]{4}$", u)
    }

    # Crawl linked pages, waiting 1s between consecutive accesses
    for specific_hazard_url in specific_hazard_urls:
        sleep(1)
        _crawl(graph, specific_hazard_url)


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
}


@cli_hip.command(name="reshape")
@click.argument("inputs", metavar="INPUT_FILE...", nargs=-1)
@click.option("-o", "--output-file", metavar="FILE", default=".ttl:-", help="output RDF file (default '.ttl:-')")
def cli_hip_reshape(inputs: list[str], output_file: str = ".ttl:-") -> None:
    """Reshape crawled HIP Abox data into the format used in CRIMA."""
    # Parse input data into a Graph
    graph = create_graph()
    for input in inputs or [".ttl:-"]:
        rdf_read(graph, input)

    # Setup prefixes, both for serialization and SPARQL transformations
    _bind_prefixes(graph)

    # Reshape the graph in multiple steps
    _reshape_types(graph)
    _reshape_iris(graph)
    _reshape_skos_triples(graph)
    _reshape_ontology_triples(graph)
    _reshape_irrelevant_triples(graph)

    # Serialize collected RDF data (to file or stdout)
    rdf_write(graph, output_file)


def _reshape_types(graph: Graph) -> None:
    """
    Reshape step #1: assign correct rdf:type(s) to ABox individuals.

    :param graph: the Graph with HIP ABox data being transformed
    """
    # Replace class prov:Entity with bibo:Document + owl:NamedIndividual
    for s in list(graph.subjects(RDF.type, PROV.Entity)):
        graph.remove((s, RDF.type, PROV.Entity))
        graph.add((s, RDF.type, OWL.NamedIndividual))
        graph.add((s, RDF.type, BIBO.Document))

    # Replace class skos:Concept with subclasses hip:{HazardCluster,HazardType,SpecificHazard} + owl:NamedIndividual
    for s, _, _ in list(graph.triples((None, RDF.type, SKOS.Concept))):
        dcterms_type = graph.value(s, DCTERMS.type)
        rdf_type = (
            HIP_SCHEMA.HazardCluster
            if dcterms_type == Literal("cluster")
            else HIP_SCHEMA.HazardType
            if dcterms_type == Literal("type")
            else HIP_SCHEMA.SpecificHazard
            if not dcterms_type
            else None
        )
        if rdf_type:
            graph.add((s, RDF.type, OWL.NamedIndividual))
            graph.remove((s, DCTERMS.type, None))
            graph.remove((s, RDF.type, SKOS.Concept))
            graph.add((s, RDF.type, rdf_type))


def _reshape_iris(graph: Graph) -> None:
    """
    Reshape step #2: rename IRIs of HIP scheme/concepts to ensure they conform to a certain form.

    :param graph: the Graph with HIP ABox data being transformed
    """
    # Dictionary where to schedule replacements
    replacements: dict[URIRef, URIRef] = {}

    # Replace <.../drr-glossary/hips> website URL with <.../drr-glossary/HIP-classification-system> scheme IRI
    replacements[WEBSITE] = SCHEME

    # Ensure hip:{HazardCluster,HazardType,SpecificHazard} IRIs are of form <correspoding namespace / local name>
    # E.g.: hip-cluster:construction/structural-failure -> hip-cluster:construction-structural-failure
    for c, ns in (
        (HIP_SCHEMA.HazardCluster, "https://www.preventionweb.net/hips-cluster/"),
        (HIP_SCHEMA.HazardType, "https://www.preventionweb.net/hips-type/"),
        (HIP_SCHEMA.SpecificHazard, "https://www.undrr.org/terms/hips/"),
    ):
        for s in graph.subjects(RDF.type, c):
            if isinstance(s, URIRef) and s.startswith(ns) and get_namespace(s) != ns:
                name = s[len(ns) :]
                name = name.replace("/", "-")
                replacements[s] = URIRef(ns + name)

    # Discard hip-schema:SpecificHazard IRIs that are referenced somewhere but lack a proper definition
    # (e.g., a dcterms:identifier, which comes from the web page defining the specific hazard - here 404)
    for s in graph.subjects(RDF.type, HIP_SCHEMA.SpecificHazard):
        if not graph.value(s, DCTERMS.identifier):
            replacements[s] = None

    # Apply replacements in a single pass over Graph triples
    replace_terms(graph, replacements, positions={0, 2})

    # Triples with predicate prov:wasInfluencedBy and dcterms:references should go to website URL, and not scheme IRI
    # (this will revert website -> scheme replacement in those specific cases only)
    for s, p, _ in graph.triples((None, None, SCHEME)):
        if p in {PROV.wasInfluencedBy, DCTERMS.references}:
            graph.remove((s, p, SCHEME))
            graph.add((s, p, WEBSITE))




def _reshape_skos_triples(graph: Graph) -> None:
    """
    Reshape step #3: curate SKOS triples describing/linking SKOS schemes/concepts.

    :param graph: the Graph with HIP Abox data being transformed
    """
    # Re-assign rdf:type(s) of the skos:Scheme individual: hip-schema:HIP-ClassificationSystem + owl:NamedIndividual
    graph.remove((SCHEME, RDF.type, None))
    graph.add((SCHEME, RDF.type, HIP_SCHEMA["HIP-ClassificationSystem"]))
    graph.add((SCHEME, RDF.type, OWL.NamedIndividual))

    # For the skos:Scheme individual, recover title, description and date from OG properties (later discarded)
    for o in graph.objects(SCHEME, OG.title):
        graph.add((SCHEME, DCTERMS.title, o))
    for o in graph.objects(SCHEME, OG.description):
        graph.add((SCHEME, DCTERMS.description, o))
    for o in graph.objects(SCHEME, ARTICLE.published_time):
        graph.add((SCHEME, DCTERMS.date, o))

    # Assert skos:inScheme triples for all instances of hip-schema:{HazardCluster,HazardType}
    for c in (HIP_SCHEMA.HazardCluster, HIP_SCHEMA.HazardType):
        for s in list(graph.subjects(RDF.type, c)):
            graph.add((s, SKOS.inScheme, URIRef(SCHEME)))

    # Replace skos:broader triples pointing to hip-schema:HazardCluster SKOS collections with clex:isMemberOf triples
    for s, _, o in list(graph.triples((None, SKOS.broader, None))):
        if (o, RDF.type, HIP_SCHEMA.HazardCluster) in graph:
            graph.remove((s, SKOS.broader, o))
            graph.add((s, CLEX.isMemberOf, o))

    # Generate missing skos:broader triples from hip-schema:HazardCluster to hip-schema:HazardType individuals (TODO)
    for r in list(
        graph.query("""
        SELECT (?hc AS ?cluster) (SAMPLE(?ht) AS ?type)
        {
            ?hc a hip-schema:HazardCluster; ^clex:isMemberOf ?st .
            ?st a hip-schema:SpecificHazard; skos:broader ?ht .
            ?ht a hip-schema:HazardType
        }
        GROUP BY ?hc
        HAVING (COUNT(DISTINCT ?ht) = 1)
        """)
    ):
        graph.add((r.cluster, SKOS.broader, r.type))


def _reshape_ontology_triples(graph: Graph) -> None:
    """
    Reshape step #4: add owl:Ontology individual and triples.

    :param graph: the Graph with HIP data being transformed
    """
    # Read ontology data from embedded RDF in Turtle syntax
    graph.parse(
        format="ttl",
        data="""
        @prefix bibo: <http://purl.org/ontology/bibo/> .
        @prefix clex: <http://www.semanticweb.org/crima/crima-lexicon#> .
        @prefix dcterms: <http://purl.org/dc/terms/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix voaf: <http://purl.org/vocommons/voaf#> .

        <https://undrr-hip.org/hip-data/> a owl:Ontology ;
            voaf:metadataVoc <http://purl.org/vocommons/voaf> ;
            voaf:reliesOn dcterms:,
                bibo:,
                <http://rdf-vocabulary.ddialliance.org/xkos>,
                clex:,
                <http://www.w3.org/2004/02/skos/core>,
                <http://www.w3.org/ns/prov-o#>,
                <https://undrr-hip.org/hip-schema/> ;
            owl:imports dcterms:,
                bibo:,
                <http://rdf-vocabulary.ddialliance.org/xkos>,
                clex:,
                <http://www.w3.org/2004/02/skos/core>,
                <http://www.w3.org/ns/prov-o#>,
                <https://undrr-hip.org/hip-schema/> .
        """,
    )


def _reshape_irrelevant_triples(graph: Graph) -> None:
    """
    Reshape step #5: drop irrelevant triples.

    :param graph: the Graph with HIP ABox data being transformed
    """
    # Drop all triples from OG, ARTICLE, XHV vocabularies
    graph.remove((None, ARTICLE.published_time, None))
    graph.remove((None, OG.description, None))
    graph.remove((None, OG.title, None))
    graph.remove((None, OG.image, None))
    graph.remove((None, XHV.role, None))

    # Add all triples about terms in <https://www.preventionweb.net/hips-chapeau/> namespace
    for t in {
        t for triple in graph for t in triple if get_namespace(t) == "https://www.preventionweb.net/hips-chapeau/"
    }:
        graph.remove((t, None, None))
        graph.remove((None, None, t))


def _bind_prefixes(graph: Graph) -> None:
    """
    Set prefixes related to HIP data, for use in RDF serialization and SPARQL transformations.

    :param graph: the Graph where to bind prefixes to
    """
    graph.bind("article", "http://ogp.me/ns/article#")
    graph.bind("clex", "http://www.semanticweb.org/crima/crima-lexicon#")
    graph.bind("dcterms", "http://purl.org/dc/terms/")
    graph.bind("hip-cluster", "https://www.preventionweb.net/hips-cluster/")
    graph.bind("hip-glossary", "https://www.preventionweb.net/drr-glossary/")
    graph.bind("hip-schema", "https://undrr-hip.org/")
    graph.bind("hip-term", "https://www.undrr.org/terms/hips/")
    graph.bind("hip-type", "https://www.preventionweb.net/hips-type/")
    graph.bind("og", "https://ogp.me/ns#")
    graph.bind("prov", "http://www.w3.org/ns/prov#")
    graph.bind("skos", "http://www.w3.org/2004/02/skos/core#")
    graph.bind("xhv", "http://www.w3.org/1999/xhtml/vocab#")
    graph.bind("xkos", "http://rdf-vocabulary.ddialliance.org/xkos#")
