from string import Template
from textwrap import dedent
from zipfile import ZIP_DEFLATED, ZipFile

import click
from rdflib import DCTERMS, URIRef

from crima_ontology_tool.util import create_graph, rdf_read


@click.group(name="cclc")
def cli_cclc() -> None:
    """Utilities related to CRIMA CORINE Land Cover (CCLC) Abox data."""


@cli_cclc.command(name="csv")
@click.argument("input_files", metavar="INPUT_FILE...", nargs=-1)
@click.option("-o", "--output-file", metavar="FILE", default="hip.zip", help="output ZIP file")
@click.option("-p", "--prefix", metavar="PREFIX", default="", help="optional prefix for generated SQL tables")
def cli_clc_csv(input_files: list[str], output_file: str, prefix: str = "") -> None:
    """
    Generate a ZIP with equivalent CSV files, SQL schema, and OBDA mappings for CCLC RDF ABox data.

    Takes one or multiple RDF input files with CCLC ABox data (e.g., modules/cclc.ttl), and an optional prefix for
    generated tables (default "") . Based on them, produces a ZIP file containing:
    (1) {prefix}{table}.csv: a CSV file per table, with CLC data (1 table total for all classes);
    (2) schema.sql: the SQL schema with table definitions matching the content CSV files, for possible import in a RDB;
    (3) mapping.obda: an OBDA mapping file, in Ontop format, formalizing the correspondence between CSV and RDF data.
    """
    graph = create_graph()
    for input in input_files or [".ttl:-"]:
        rdf_read(graph, input)

    graph.bind("skos", "http://www.w3.org/2004/02/skos/core#")
    graph.bind("cclc", "http://www.semanticweb.org/crima/crima-clc#")

    with ZipFile(output_file, mode="w", compression=ZIP_DEFLATED) as zip:

        def emit_csv(tbl_suffix: str, query: str) -> None:
            results = graph.query(query)
            with zip.open(prefix + tbl_suffix + ".csv", "w") as f:
                results.serialize(destination=f, format="csv")

        with zip.open("schema.sql", "w") as f:
            f.write(dedent(_CCLC_SQL_TEMPLATE.substitute(prefix=prefix)).lstrip().encode("utf-8"))

        with zip.open("mapping.obda", "w") as f:
            template_args = {
                "prefix": prefix,
                "title": graph.value(_CCLC_SCHEME, DCTERMS.title).value,
                "description": graph.value(_CCLC_SCHEME, DCTERMS.description).value,
                "issued": graph.value(_CCLC_SCHEME, DCTERMS.issued).value,
                "modified": graph.value(_CCLC_SCHEME, DCTERMS.modified).value,
            }
            f.write(dedent(_CCLC_OBDA_TEMPLATE.substitute(**template_args)).lstrip().encode("utf-8"))

        emit_csv(
            "class",
            """
            SELECT ?id ?level ?parent1_id ?parent2_id ?label_en ?label_sk ?definition_en ?notation
            {
                {
                    ?iri a cclc:CORINE-Class_level1
                    BIND (1 AS ?level)
                } UNION {
                    ?iri a cclc:CORINE-Class_level2 ; skos:broader ?parent1_iri .
                    BIND (2 AS ?level)
                } UNION {
                    ?iri a cclc:CORINE-Class_level3 ; skos:broader ?parent2_iri .
                    ?parent2_iri skos:broader ?parent1_iri .
                    BIND (3 AS ?level)
                }
                ?iri skos:prefLabel ?label_en , ?label_sk ;
                    skos:definition ?definition_en ;
                    skos:notation ?notation .
                FILTER (LANG(?label_en) = "en")
                FILTER (LANG(?label_sk) = "sk")
                BIND(STRAFTER(STRAFTER(STR(?iri), STR(cclc:)), "clc") AS ?id)
                BIND(STRAFTER(STRAFTER(STR(?parent1_iri), STR(cclc:)), "clc") AS ?parent1_id)
                BIND(STRAFTER(STRAFTER(STR(?parent2_iri), STR(cclc:)), "clc") AS ?parent2_id)
            }
            ORDER BY ?id""",
        )


_CCLC_SCHEME = URIRef("http://www.semanticweb.org/crima/crima-clc#corine-land-cover-classification")


_CCLC_SQL_TEMPLATE = Template("""
    CREATE TABLE ${prefix}class (
        id SMALLINT NOT NULL,
        level SMALLINT NOT NULL,
        parent1_id SMALLINT,
        parent2_id SMALLINT,
        label_en VARCHAR NOT NULL,
        label_sk VARCHAR NOT NULL,
        definition_en VARCHAR NOT NULL,
        notation VARCHAR NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY (parent1_id) REFERENCES ${prefix}class(id),
        FOREIGN KEY (parent2_id) REFERENCES ${prefix}class(id)
    );
""")


_CCLC_OBDA_TEMPLATE = Template("""
    [PrefixDeclaration]
    cc:         http://creativecommons.org/ns#>
    cclc:       http://www.semanticweb.org/crima/crima-clc#>
    dcterms:    http://purl.org/dc/terms/
    owl:        http://www.w3.org/2002/07/owl#
    skos:       http://www.w3.org/2004/02/skos/core#
    vann:       http://purl.org/vocab/vann/>
    xsd:        http://www.w3.org/2001/XMLSchema#

    [MappingDeclaration] @collection [[

    mappingId   ${prefix}static
    target      <http://www.semanticweb.org/crima/crima-clc-data#> a owl:Ontology ;
                    owl:imports <http://www.w3.org/2004/02/skos/core> , <http://www.semanticweb.org/crima/crima-clc#> ;
                    vann:preferredNamespacePrefix "cclc" ;
                    vann:preferredNamespaceUri "http://www.semanticweb.org/crima/crima-clc#"^^xsd:anyURI .
                cclc:corine-land-cover-classification a cclc:CORINE-classification ;
                    cc:license <https://creativecommons.org/publicdomain/zero/1.0/> ;
                    dcterms:title "${title}"@en ;
                    dcterms:description "${description}"@en ;
                    dcterms:issued "${issued}"^^xsd:date ;
                    dcterms:modified "${modified}"^^xsd:date ;
                    dcterms:source "http://sia.eionet.europa.eu/CLC2000/classes"^^xsd:anyURI .
    source      SELECT 1

    mappingId   ${prefix}class
    target      cclc:clc{id}
                    skos:notation "{notation}"^^cclc:CorineValue ;
                    skos:prefLabel "{label_en}"@en , "{label_sk}"@sk ;
                    skos:definition "{definition_en}"@en ;
                    skos:broaderTransitive cclc:clc{parent1_id} , cclc:clc{parent2_id} ;
                    skos:inScheme cclc:corine-land-cover-classification .
    source      SELECT * FROM ${prefix}class

    mappingId   ${prefix}class-level1
    target      cclc:clc{id} a cclc:CORINE-Class_level1 .
    source      SELECT * FROM ${prefix}class WHERE level = 1

    mappingId   ${prefix}class-level2
    target      cclc:clc{id} a cclc:CORINE-Class_level2 ; skos:broader cclc:clc{parent1_id} .
    source      SELECT * FROM ${prefix}class WHERE level = 2

    mappingId   ${prefix}class-level3
    target      cclc:clc{id} a cclc:CORINE-Class_level3 ; skos:broader cclc:clc{parent2_id} .
    source      SELECT * FROM ${prefix}class WHERE level = 3
    ]]
""")
