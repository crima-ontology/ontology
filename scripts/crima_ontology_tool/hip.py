import json
import logging
import re
from hashlib import blake2b
from string import Template
from textwrap import dedent
from time import sleep
from urllib.parse import urljoin
from zipfile import ZIP_DEFLATED, ZipFile

import click
import extruct
import requests
from lxml import html
from rdflib import DCTERMS, OWL, RDF, RDFS, SKOS, XSD, Graph, Literal, Namespace, URIRef

from crima_ontology_tool.util import BIBO, PROV, create_graph, get_namespace, rdf_read, rdf_write, replace_terms

_LOGGER = logging.getLogger(__name__)


ARTICLE = Namespace("http://ogp.me/ns/article#")
HIP_SCHEMA = Namespace("https://undrr-hip.org/")
OG = Namespace("https://ogp.me/ns#")
XHV = Namespace("http://www.w3.org/1999/xhtml/vocab#")
XKOS = Namespace("http://rdf-vocabulary.ddialliance.org/xkos#")

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
    _reshape_terms(graph)
    _reshape_skos_triples(graph)
    _reshape_ontology_triples(graph)
    _reshape_irrelevant_triples(graph)
    _reshape_datatypes(graph)

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
    for s in list(graph.subjects(RDF.type, SKOS.Concept)):
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

    # Add type bibo:Image and remove bibo:Document (super-class) to subjects of dcterms:type "diagram"
    for s in graph.subjects(DCTERMS.type, Literal("diagram")):
        graph.remove((s, DCTERMS.type, None))
        graph.add((s, RDF.type, BIBO.Image))

    # Add class skos:Concept to objects of skos:related property
    for o in list(graph.objects(predicate=SKOS.related)):
        graph.add((o, RDF.type, SKOS.Concept))


def _reshape_terms(graph: Graph) -> None:
    """
    Reshape step #2: rewrite terms (IRIs/literals) of HIP scheme/concepts to ensure they conform to a certain form.

    :param graph: the Graph with HIP ABox data being transformed
    """
    # Dictionary where to schedule replacements
    replacements: dict[URIRef, URIRef] = {}

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

    # Replace bibo:Document/bibo:Image arbitrary IRIs with a templated one, moving original IRI as bibo:uri value
    for s in set(graph.subjects(RDF.type, BIBO.Document)) | set(graph.subjects(RDF.type, BIBO.Image)):
        iri = graph.value(s, DCTERMS.identifier) or str(s)
        graph.remove((s, DCTERMS.identifier, None))
        graph.add((s, BIBO.uri, Literal(iri, datatype=XSD.anyURI)))
        hash = blake2b(iri.encode("utf-8"), digest_size=8).hexdigest()
        iri = URIRef("https://www.preventionweb.net/hips-document/" + hash)
        replacements[s] = iri
        replacements[Literal(s)] = iri  # this handles objects of dcterms:conformsTo that are literals rather than IRIs

    # Apply replacements in a single pass over Graph triples
    replace_terms(graph, replacements, positions={0, 2})


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
    website_document_iri = next(graph.subjects(BIBO.uri, Literal(WEBSITE, datatype=XSD.anyURI)))
    for o in graph.objects(website_document_iri, OG.title):
        graph.add((SCHEME, DCTERMS.title, o))
    for o in graph.objects(website_document_iri, OG.description):
        graph.add((SCHEME, DCTERMS.description, o))
    for o in graph.objects(website_document_iri, ARTICLE.published_time):
        graph.add((SCHEME, DCTERMS.date, o))

    # Assert skos:inScheme triples for all instances of hip-schema:{HazardCluster,HazardType}
    for c in (HIP_SCHEMA.HazardCluster, HIP_SCHEMA.HazardType, HIP_SCHEMA.SpecificHazard):
        for s in list(graph.subjects(RDF.type, c)):
            graph.remove((s, SKOS.inScheme, None))
            graph.add((s, SKOS.inScheme, URIRef(SCHEME)))

    # Generate missing skos:broader triples from hip-schema:HazardCluster to hip-schema:HazardType individuals
    for r in list(
        graph.query("""
        SELECT (?hc AS ?cluster) (SAMPLE(?ht) AS ?type)
        {
            ?sh a hip-schema:SpecificHazard; skos:broader ?hc , ?ht .
            ?hc a hip-schema:HazardCluster .
            ?ht a hip-schema:HazardType
        }
        GROUP BY ?hc
        HAVING (COUNT(DISTINCT ?ht) = 1)
        """)
    ):
        graph.add((r.cluster, SKOS.broader, r.type))

    # Materialize xkos:causes / xkos:causedBy as inverse of each other
    for s, _, o in list(graph.triples((None, XKOS.causes, None))):
        graph.add((o, XKOS.causedBy, s))
    for s, _, o in list(graph.triples((None, XKOS.causedBy, None))):
        graph.add((o, XKOS.causes, s))


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
        @prefix dcterms: <http://purl.org/dc/terms/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix voaf: <http://purl.org/vocommons/voaf#> .

        <https://undrr-hip.org/hip-data/> a owl:Ontology ;
            voaf:metadataVoc <http://purl.org/vocommons/voaf> ;
            voaf:reliesOn dcterms:,
                bibo:,
                <http://rdf-vocabulary.ddialliance.org/xkos>,
                <http://www.w3.org/2004/02/skos/core>,
                <http://www.w3.org/ns/prov-o#>,
                <https://undrr-hip.org/hip-schema/> ;
            owl:imports dcterms:,
                bibo:,
                <http://rdf-vocabulary.ddialliance.org/xkos>,
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

    # Drop all triples about terms in <https://www.preventionweb.net/hips-chapeau/> namespace
    for t in {
        t for triple in graph for t in triple if get_namespace(t) == "https://www.preventionweb.net/hips-chapeau/"
    }:
        graph.remove((t, None, None))
        graph.remove((None, None, t))

    # Drop all extra rdfs:label of bibo:Document instances except the longest one
    for s in graph.subjects(RDF.type, BIBO.Document):
        labels = set(graph.objects(s, RDFS.label))
        if len(labels) > 1:
            graph.remove((s, RDFS.label, None))
            graph.add((s, RDFS.label, max(sorted(labels), key=lambda l: len(l.value))))

    # Drop triples with empty literals
    to_drop = []
    for triple in graph:
        o = triple[2]
        if isinstance(o, Literal) and o.value == "":
            to_drop.append(triple)
    for triple in to_drop:
        graph.remove(triple)


def _reshape_datatypes(graph: Graph) -> None:
    """
    Reshape step #6: assign proper literal datatypes (e.g., xsd:dateTime for dcterms:date and similar).

    :param graph: the Graph with HIP ABox data being transformed
    """
    # Use xsd:dateTime as datatype of literal objects of dcterms:{date,created,modified}
    for p in (DCTERMS.date, DCTERMS.created, DCTERMS.modified):
        for s, _, o in list(graph.triples((None, p, None))):
            if isinstance(o, Literal) and o.datatype != XSD.dateTime:
                graph.remove((s, p, o))
                graph.add((s, p, Literal(o.value, datatype=XSD.dateTime)))

    # Use @en as language of literal objects of dcterms:{title,description,accessRights}
    for p in (DCTERMS.title, DCTERMS.description, DCTERMS.accessRights):
        for s, _, o in list(graph.triples((None, p, None))):
            if isinstance(o, Literal) and o.language != "en":
                graph.remove((s, p, o))
                graph.add((s, p, Literal(o.value, lang="en")))


@cli_hip.command(name="csv")
@click.argument("input_files", metavar="INPUT_FILE...", nargs=-1)
@click.option("-o", "--output-file", metavar="FILE", default="hip.zip", help="output ZIP file")
@click.option("-p", "--prefix", metavar="PREFIX", default="", help="optional prefix for generated SQL tables")
def cli_hip_csv(input_files: list[str], output_file: str, prefix: str = "") -> None:
    """
    Generate a ZIP with equivalent CSV files, SQL schema, and OBDA mappings for HIP RDF ABox data.

    Takes one or multiple RDF input files with HIP ABox data (e.g., modules/hip-data.ttl), and an optional prefix for
    generated tables (default "") . Based on them, produces a ZIP file containing:
    (1) {prefix}{table}.csv: a CSV file per table, with HIP data (9 tables total);
    (2) schema.sql: the SQL schema with table definitions matching the content CSV files, for possible import in a RDB;
    (3) mapping.obda: an OBDA mapping file, in Ontop format, formalizing the correspondence between CSV and RDF data.
    """
    graph = create_graph()
    for input in input_files or [".ttl:-"]:
        rdf_read(graph, input)

    _bind_prefixes(graph)

    with ZipFile(output_file, mode="w", compression=ZIP_DEFLATED) as zip:

        def emit_csv(tbl_suffix: str, query: str) -> None:
            results = graph.query(query)
            with zip.open(prefix + tbl_suffix + ".csv", "w") as f:
                results.serialize(destination=f, format="csv")

        with zip.open("schema.sql", "w") as f:
            f.write(dedent(_HIP_SQL_TEMPLATE.substitute(prefix=prefix)).lstrip().encode("utf-8"))

        with zip.open("mapping.obda", "w") as f:
            template_args = {
                "prefix": prefix,
                "date": graph.value(SCHEME, DCTERMS.date).value,
                "title": graph.value(SCHEME, DCTERMS.title).value,
                "description": graph.value(SCHEME, DCTERMS.description).value,
                "version": "2025 update; https://www.undrr.org/publication/"
                "2025-update-undrr-isc-hazard-information-profiles-hips",
            }
            f.write(dedent(_HIP_OBDA_TEMPLATE.substitute(**template_args)).lstrip().encode("utf-8"))

        emit_csv(
            "document",
            """
            SELECT ?id ?url ?format ?access_rights ?label {
                ?iri bibo:uri ?url .
                OPTIONAL { ?iri dcterms:format ?format }
                OPTIONAL { ?iri dcterms:accessRights ?access_rights }
                OPTIONAL { ?iri rdfs:label ?label }
                BIND(STRAFTER(STR(?iri), STR(hip-document:)) AS ?id)
            } ORDER BY ?id""",
        )

        emit_csv(
            "substance",
            """
            SELECT ?id ?label {
                ?iri a skos:Concept ; rdfs:label ?label
                FILTER (STRSTARTS(STR(?iri), "https://unece.org/transport/dangerous-goods/ghs-rev10-2023#"))
                BIND (STRAFTER(STR(?iri), "https://unece.org/transport/dangerous-goods/ghs-rev10-2023#") AS ?id)
            } ORDER BY ?id""",
        )

        emit_csv(
            "hazard_type",
            """
            SELECT  ?id ?label {
                ?iri a hip-schema:HazardType ; skos:prefLabel ?label
                BIND (STRAFTER(STR(?iri), STR(hip-type:)) AS ?id)
            } ORDER BY ?id""",
        )

        emit_csv(
            "hazard_cluster",
            """
            SELECT ?id ?hazard_type_id ?label {
                ?iri a hip-schema:HazardCluster ; skos:broader ?hazard_type ; skos:prefLabel ?label
                BIND (STRAFTER(STR(?iri), STR(hip-cluster:)) AS ?id)
                BIND (STRAFTER(STR(?hazard_type), STR(hip-type:)) AS ?hazard_type_id)
            } ORDER BY ?id""",
        )

        emit_csv(
            "specific_hazard",
            """
            SELECT DISTINCT ?id ?hazard_type_id ?hazard_cluster_id ?label ?definition ?note ?note_drivers ?note_impacts
                ?note_metrics ?note_monitoring_early_warning ?note_multi_hazard_context ?note_risk_management
                ?created ?modified ?relation
            {
                ?iri a hip-schema:SpecificHazard ;
                    skos:broader ?hazard_cluster ;
                    skos:prefLabel ?label ;
                    skos:definition ?definition ;
                    skos:note ?note ;
                    dcterms:created ?created ;
                    dcterms:modified ?modified .
                ?hazard_cluster a hip-schema:HazardCluster ;
                    skos:broader ?hazard_type .
                ?hazard_type a hip-schema:HazardType .
                OPTIONAL { ?iri dcterms:relation ?relation }
                OPTIONAL { ?iri skos:scopeNote [ dcterms:type "drivers" ; xkos:plainText ?note_drivers ] }
                OPTIONAL { ?iri skos:scopeNote [ dcterms:type "impacts" ; xkos:plainText ?note_impacts ] }
                OPTIONAL { ?iri skos:scopeNote [ dcterms:type "metrics" ; xkos:plainText ?note_metrics ] }
                OPTIONAL { ?iri skos:scopeNote [ dcterms:type "monitoringEarlyWarning" ;
                                                 xkos:plainText ?note_monitoring_early_warning ] }
                OPTIONAL { ?iri skos:scopeNote [ dcterms:type "multiHazardContext" ;
                                                 xkos:plainText ?note_multi_hazard_context ] }
                OPTIONAL { ?iri skos:scopeNote [ dcterms:type "riskManagement" ;
                                                 xkos:plainText ?note_risk_management ] }
                BIND (STRAFTER(STR(?iri), STR(hip-term:)) AS ?id)
                BIND (STRAFTER(STR(?hazard_type), STR(hip-type:)) AS ?hazard_type_id)
                BIND (STRAFTER(STR(?hazard_cluster), STR(hip-cluster:)) AS ?hazard_cluster_id)
            }
            ORDER BY ?id""",
        )

        emit_csv(
            "specific_hazard_alt_label",
            """
            SELECT ?specific_hazard_id ?alt_label {
                ?iri a hip-schema:SpecificHazard ; skos:altLabel ?alt_label
                BIND (STRAFTER(STR(?iri), STR(hip-term:)) AS ?specific_hazard_id)
            } ORDER BY ?specific_hazard_id ?alt_label""",
        )

        emit_csv(
            "specific_hazard_cause",
            """
            SELECT DISTINCT ?cause_id ?effect_id {
                ?cause a hip-schema:SpecificHazard .
                ?effect a hip-schema:SpecificHazard .
                { ?cause xkos:causes ?effect } UNION { ?effect xkos:causedBy ?cause }
                BIND (STRAFTER(STR(?cause), STR(hip-term:)) AS ?cause_id)
                BIND (STRAFTER(STR(?effect), STR(hip-term:)) AS ?effect_id)
            } ORDER BY ?cause_id ?effect_id""",
        )

        emit_csv(
            "specific_hazard_document",
            """
            SELECT
                ?specific_hazard_id ?document_id
                (MAX(?r = dcterms:conformsTo) AS ?rel_conforms_to)
                (MAX(?r = dcterms:references) AS ?rel_references)
                (MAX(?r = dcterms:source) AS ?rel_source)
                (MAX(?r = dcterms:hasPart) AS ?rel_image)
            {
                SELECT ?specific_hazard_id ?document_id ?r {
                    ?iri a hip-schema:SpecificHazard
                    { ?iri dcterms:conformsTo ?document BIND (dcterms:conformsTo AS ?r) } UNION
                    { ?iri dcterms:references ?document BIND (dcterms:references AS ?r) } UNION
                    { ?iri dcterms:source ?document BIND (dcterms:source AS ?r) } UNION
                    { ?iri dcterms:hasPart ?document BIND (dcterms:hasPart AS ?r) }
                    BIND (STRAFTER(STR(?iri), STR(hip-term:)) AS ?specific_hazard_id)
                    BIND (STRAFTER(STR(?document), STR(hip-document:)) AS ?document_id)
                }
            }
            GROUP BY ?specific_hazard_id ?document_id
            ORDER BY ?specific_hazard_id ?document_id""",
        )

        emit_csv(
            "specific_hazard_substance",
            """
            SELECT ?specific_hazard_id ?substance_id {
                ?iri a hip-schema:SpecificHazard ; skos:related ?substance
                BIND (STRAFTER(STR(?iri), STR(hip-term:)) AS ?specific_hazard_id)
                BIND (STRAFTER(STR(?substance), "https://unece.org/transport/dangerous-goods/ghs-rev10-2023#")
                      AS ?substance_id)
            } ORDER BY ?specific_hazard_id ?substance_id""",
        )


_HIP_SQL_TEMPLATE = Template("""
    CREATE TABLE ${prefix}document (
        id VARCHAR NOT NULL,
        url VARCHAR NOT NULL,
        format VARCHAR,
        access_rights VARCHAR,
        label VARCHAR,
        PRIMARY KEY (id),
        UNIQUE (url)
    );

    CREATE TABLE ${prefix}substance (
        id VARCHAR NOT NULL,
        label VARCHAR NOT NULL,
        PRIMARY KEY (id)
    );

    CREATE TABLE ${prefix}hazard_type (
        id VARCHAR NOT NULL,
        label VARCHAR NOT NULL,
        PRIMARY KEY (id)
    );

    CREATE TABLE ${prefix}hazard_cluster (
        id VARCHAR NOT NULL,
        hazard_type_id VARCHAR NOT NULL,
        label VARCHAR NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY (hazard_type_id) REFERENCES ${prefix}hazard_type(id)
    );

    CREATE TABLE ${prefix}specific_hazard (
        id VARCHAR NOT NULL,
        hazard_type_id VARCHAR NOT NULL,
        hazard_cluster_id VARCHAR NOT NULL,
        label VARCHAR NOT NULL,
        definition VARCHAR NOT NULL,
        note VARCHAR NOT NULL,
        note_drivers VARCHAR,
        note_impacts VARCHAR,
        note_metrics VARCHAR,
        note_monitoring_early_warning VARCHAR,
        note_multi_hazard_context VARCHAR,
        note_risk_management VARCHAR,
        created TIMESTAMP WITH TIME ZONE NOT NULL,
        modified TIMESTAMP WITH TIME ZONE NOT NULL,
        relation VARCHAR,
        PRIMARY KEY (id),
        FOREIGN KEY (hazard_type_id) REFERENCES ${prefix}hazard_type(id),
        FOREIGN KEY (hazard_cluster_id) REFERENCES ${prefix}hazard_cluster(id)
    );

    CREATE TABLE ${prefix}specific_hazard_alt_label (
        specific_hazard_id VARCHAR NOT NULL,
        alt_label VARCHAR NOT NULL,
        PRIMARY KEY (specific_hazard_id, alt_label),
        FOREIGN KEY (specific_hazard_id) REFERENCES ${prefix}specific_hazard(id)
    );

    CREATE TABLE ${prefix}specific_hazard_cause (
        cause_id VARCHAR NOT NULL,
        effect_id VARCHAR NOT NULL,
        PRIMARY KEY (cause_id, effect_id),
        FOREIGN KEY (cause_id) REFERENCES ${prefix}specific_hazard(id),
        FOREIGN KEY (effect_id) REFERENCES ${prefix}specific_hazard(id)
    );

    CREATE TABLE ${prefix}specific_hazard_document (
        specific_hazard_id VARCHAR NOT NULL,
        document_id VARCHAR NOT NULL,
        rel_conforms_to BOOLEAN NOT NULL,
        rel_references BOOLEAN NOT NULL,
        rel_source BOOLEAN NOT NULL,
        rel_image BOOLEAN NOT NULL,
        PRIMARY KEY (specific_hazard_id, document_id),
        FOREIGN KEY (specific_hazard_id) REFERENCES ${prefix}specific_hazard(id),
        FOREIGN KEY (document_id) REFERENCES ${prefix}document(id)
    );

    CREATE TABLE ${prefix}specific_hazard_substance (
        specific_hazard_id VARCHAR NOT NULL,
        substance_id VARCHAR NOT NULL,
        PRIMARY KEY (specific_hazard_id, substance_id),
        FOREIGN KEY (specific_hazard_id) REFERENCES ${prefix}specific_hazard(id),
        FOREIGN KEY (substance_id) REFERENCES ${prefix}substance(id)
    );
""")


_HIP_OBDA_TEMPLATE = Template("""
    [PrefixDeclaration]
    bibo:           http://purl.org/ontology/bibo/
    dcterms:        http://purl.org/dc/terms/
    hip-cluster:    https://www.preventionweb.net/hips-cluster/
    hip-document:   https://www.preventionweb.net/hips-document/
    hip-glossary:   https://www.preventionweb.net/drr-glossary/
    hip-schema:     https://undrr-hip.org/
    hip-term:       https://www.undrr.org/terms/hips/
    hip-type:       https://www.preventionweb.net/hips-type/
    owl:            http://www.w3.org/2002/07/owl#
    prov:           http://www.w3.org/ns/prov#
    rdf:            http://www.w3.org/1999/02/22-rdf-syntax-ns#
    rdfs:           http://www.w3.org/2000/01/rdf-schema#
    skos:           http://www.w3.org/2004/02/skos/core#
    voaf:           http://purl.org/vocommons/voaf#
    xsd:            http://www.w3.org/2001/XMLSchema#
    xkos:           http://rdf-vocabulary.ddialliance.org/xkos#

    [MappingDeclaration] @collection [[

    mappingId   ${prefix}static
    target      hip-glossary:HIP-classification-system a hip-schema:HIP-ClassificationSystem ;
                    dcterms:date "${date}"^^xsd:dateTime ;
                    dcterms:title "${title}"@en ;
                    dcterms:description "${description}"@en .
                <https://undrr-hip.org/hip-data/> a owl:Ontology ;
                    voaf:metadataVoc <http://purl.org/vocommons/voaf> ;
                    voaf:reliesOn
                        <http://purl.org/dc/terms/> ,
                        <http://purl.org/ontology/bibo/> ,
                        <http://rdf-vocabulary.ddialliance.org/xkos> ,
                        <http://www.w3.org/2004/02/skos/core> ,
                        <http://www.w3.org/ns/prov-o#> ,
                        <https://undrr-hip.org/hip-schema/> ;
                    owl:imports
                        <http://purl.org/dc/terms/> ,
                        <http://purl.org/ontology/bibo/> ,
                        <http://rdf-vocabulary.ddialliance.org/xkos> ,
                        <http://www.w3.org/2004/02/skos/core> ,
                        <http://www.w3.org/ns/prov-o#> ,
                        <https://undrr-hip.org/hip-schema/> .
    source      SELECT 1

    mappingId   ${prefix}document
    target      hip-document:{id} a bibo:Document ;
                    bibo:uri {url}^^xsd:anyURI ;
                    rdfs:label "{label}"@en ;
                    dcterms:format "{format}" ;
                    dcterms:accessRights "{access_rights}"@en .
    source      SELECT * FROM ${prefix}document

    mappingId   ${prefix}document_image
    target      hip-document:{id} a bibo:Image .
    source      SELECT * FROM ${prefix}document WHERE format = 'image/png'

    mappingId   ${prefix}subdomain
    target      <https://unece.org/transport/dangerous-goods/ghs-rev10-2023#{id}> a skos:Concept ;
                    rdfs:label "{label}"@en .
    source      SELECT * FROM ${prefix}substance

    mappingId   ${prefix}hazard_type
    target      hip-type:{id} a hip-schema:HazardType ;
                    skos:prefLabel "{label}"@en ;
                    skos:inScheme hip-glossary:HIP-classification-system .
    source      SELECT * FROM ${prefix}hazard_type

    mappingId   ${prefix}hazard_cluster
    target      hip-cluster:{id} a hip-schema:HazardCluster ;
                    skos:prefLabel "{label}"@en ;
                    skos:inScheme hip-glossary:HIP-classification-system ;
                    skos:broader hip-type:{hazard_type_id} .
    source      SELECT * FROM ${prefix}hazard_cluster

    mappingId   ${prefix}specific_hazard
    target      hip-term:{id} a hip-schema:SpecificHazard ;
                    skos:prefLabel "{label}"@en ;
                    dcterms:title "{label}"@en ;
                    skos:definition "{definition}"@en ;
                    skos:note "{note}"@en ;
                    dcterms:identifier "{id_upper}" ;
                    dcterms:created "{created}"^^xsd:dateTime ;
                    dcterms:modified "{modified}"^^xsd:dateTime ;
                    dcterms:relation "{relation}"@en ;
                    dcterms:publisher "UNDRR, ISC, and contributors" ;
                    dcterms:rights "Creative Commons CC BY 4.0" ;
                    owl:versionInfo "${version}"@en ;
                    skos:inScheme hip-glossary:HIP-classification-system ;
                    skos:broader hip-cluster:{hazard_cluster_id} ;
                    skos:broaderTransitive hip-type:{hazard_type_id} .
    source      SELECT *, upper(id) AS id_upper FROM ${prefix}specific_hazard

    mappingId   unibz_hip_specific_hazard_note_drivers
    target      hip-term:{id} skos:scopeNote _:{id}/note-drivers .
                _:{id}/note-drivers a xkos:ExplanatoryNote ;
                    dcterms:type "drivers" ;
                    xkos:plainText "{note_drivers}"@en .
    source      SELECT * FROM unibz_hip_specific_hazard WHERE note_drivers IS NOT NULL

    mappingId   unibz_hip_specific_hazard_note_impacts
    target      hip-term:{id} skos:scopeNote _:{id}/note-impacts .
                _:{id}/note-impacts a xkos:ExplanatoryNote ;
                    dcterms:type "impacts" ;
                    xkos:plainText "{note_impacts}"@en .
    source      SELECT * FROM unibz_hip_specific_hazard WHERE note_impacts IS NOT NULL

    mappingId   unibz_hip_specific_hazard_note_metrics
    target      hip-term:{id} skos:scopeNote _:{id}/note-metrics .
                _:{id}/note-metrics a xkos:ExplanatoryNote ;
                    dcterms:type "metrics" ;
                    xkos:plainText "{note_metrics}"@en .
    source      SELECT * FROM unibz_hip_specific_hazard WHERE note_metrics IS NOT NULL

    mappingId   unibz_hip_specific_hazard_note_monitoring_early_warning
    target      hip-term:{id} skos:scopeNote _:{id}/note-monitoring-early-warning .
                _:{id}/note-monitoring-early-warning a xkos:ExplanatoryNote ;
                    dcterms:type "monitoringEarlyWarning" ;
                    xkos:plainText "{note_monitoring_early_warning}"@en .
    source      SELECT * FROM unibz_hip_specific_hazard WHERE note_monitoring_early_warning IS NOT NULL

    mappingId   unibz_hip_specific_hazard_note_multi_hazard_context
    target      hip-term:{id} skos:scopeNote _:{id}/note-multi-hazard-context .
                _:{id}/note-multi-hazard-context a xkos:ExplanatoryNote ;
                    dcterms:type "multiHazardContext" ;
                    xkos:plainText "{note_multi_hazard_context}"@en .
    source      SELECT * FROM unibz_hip_specific_hazard WHERE note_multi_hazard_context IS NOT NULL

    mappingId   unibz_hip_specific_hazard_note_risk_management
    target      hip-term:{id} skos:scopeNote _:{id}/note-risk-management .
                _:{id}/note-risk-management a xkos:ExplanatoryNote ;
                    dcterms:type "riskManagement" ;
                    xkos:plainText "{note_risk_management}"@en .
    source      SELECT * FROM unibz_hip_specific_hazard WHERE note_risk_management IS NOT NULL

    mappingId   ${prefix}specific_hazard_alt_label
    target      hip-term:{specific_hazard_id} skos:altLabel "{alt_label}"@en .
    source      SELECT * FROM ${prefix}specific_hazard_alt_label

    mappingId   ${prefix}specific_hazard_cause
    target      hip-term:{cause_id} xkos:causes hip-term:{effect_id} .
                hip-term:{effect_id} xkos:causedBy hip-term:{cause_id} .
    source      SELECT * FROM ${prefix}specific_hazard_cause

    mappingId   unibz_hip_specific_hazard_document
    target      hip-term:{specific_hazard_id} dcterms:relation hip-document:{document_id} .
    source      SELECT * FROM unibz_hip_specific_hazard_document

    mappingId   ${prefix}specific_hazard_document_conforms_to
    target      hip-term:{specific_hazard_id} dcterms:conformsTo hip-document:{document_id} .
    source      SELECT * FROM ${prefix}specific_hazard_document WHERE rel_conforms_to = TRUE

    mappingId   ${prefix}specific_hazard_document_references
    target      hip-term:{specific_hazard_id} dcterms:references hip-document:{document_id} .
                hip-term:{specific_hazard_id} prov:wasInfluencedBy hip-document:{document_id} .
    source      SELECT * FROM ${prefix}specific_hazard_document WHERE rel_references = TRUE

    mappingId   ${prefix}specific_hazard_document_source
    target      hip-term:{specific_hazard_id} dcterms:source hip-document:{document_id} .
                hip-term:{specific_hazard_id} prov:wasQuotedFrom hip-document:{document_id} .
    source      SELECT * FROM ${prefix}specific_hazard_document WHERE rel_source = TRUE

    mappingId   ${prefix}specific_hazard_document_image
    target      hip-term:{specific_hazard_id} dcterms:hasPart hip-document:{document_id} .
    source      SELECT * FROM ${prefix}specific_hazard_document WHERE rel_image = TRUE

    mappingId   ${prefix}specific_hazard_substance
    target      hip-term:{specific_hazard_id} skos:related
                    <https://unece.org/transport/dangerous-goods/ghs-rev10-2023#{substance_id}> .
    source      SELECT * FROM ${prefix}specific_hazard_substance

    ]]
""")


def _bind_prefixes(graph: Graph) -> None:
    """
    Set prefixes related to HIP data, for use in RDF serialization and SPARQL transformations.

    :param graph: the Graph where to bind prefixes to
    """
    graph.bind("article", "http://ogp.me/ns/article#")
    graph.bind("bibo", "http://purl.org/ontology/bibo/")
    graph.bind("dcterms", "http://purl.org/dc/terms/")
    graph.bind("hip-cluster", "https://www.preventionweb.net/hips-cluster/")
    graph.bind("hip-glossary", "https://www.preventionweb.net/drr-glossary/")
    graph.bind("hip-schema", "https://undrr-hip.org/")
    graph.bind("hip-term", "https://www.undrr.org/terms/hips/")
    graph.bind("hip-type", "https://www.preventionweb.net/hips-type/")
    graph.bind("hip-document", "https://www.preventionweb.net/hips-document/")
    graph.bind("og", "https://ogp.me/ns#")
    graph.bind("prov", "http://www.w3.org/ns/prov#")
    graph.bind("skos", "http://www.w3.org/2004/02/skos/core#")
    graph.bind("xhv", "http://www.w3.org/1999/xhtml/vocab#")
    graph.bind("xkos", "http://rdf-vocabulary.ddialliance.org/xkos#")
