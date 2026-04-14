from string import Template
from textwrap import dedent
from zipfile import ZIP_DEFLATED, ZipFile

import click

from crima_vkg_tool.util import create_graph, rdf_read


@click.command(name="ecv")
@click.argument("input_file", metavar="INPUT_FILE")
@click.option("-o", "--output-file", metavar="FILE", default="ecv.zip", help="output ZIP file")
@click.option("-p", "--prefix", metavar="PREFIX", default="", help="optional prefix for generated SQL tables")
def cli_ecv(input_file: str, output_file: str, prefix: str = "") -> None:
    """
    Generate a ZIP with equivalent CSV files, SQL schema, and OBDA mappings for ECV RDF data.

    Takes one or multiple RDF input files with ECV ABox data (e.g., modules/ecv-data.ttl), and an optional prefix for
    generated tables (default "") . Based on them, produces a ZIP file containing:
    (1) {prefix}{table}.csv: a CSV file per table, with ECV data (6 tables total);
    (2) schema.sql: the SQL schema with table definitions matching the content CSV files, for possible import in a RDB;
    (3) mapping.obda: an OBDA mapping file, in Ontop format, formalizing the correspondence between CSV and RDF data.
    """
    graph = create_graph()
    rdf_read(graph, input_file)

    with ZipFile(output_file, mode="w", compression=ZIP_DEFLATED) as zip:

        def emit_csv(tbl_suffix: str, query: str) -> None:
            results = graph.query(query)
            with zip.open(prefix + tbl_suffix + ".csv", "w") as f:
                results.serialize(destination=f, format="csv")

        with zip.open("schema.sql", "w") as f:
            f.write(dedent(_ECV_SQL_TEMPLATE.substitute(prefix=prefix)).lstrip().encode("utf-8"))

        with zip.open("mapping.obda", "w") as f:
            f.write(dedent(_ECV_OBDA_TEMPLATE.substitute(prefix=prefix)).lstrip().encode("utf-8"))

        emit_csv(
            "domain",
            """
            SELECT ?id ?label {
                ?iri a ecv:ECV-domain ; rdfs:label ?label
                BIND(STRAFTER(STR(?iri), STR(ecv:)) AS ?id)
            } ORDER BY ?id""",
        )

        emit_csv(
            "subdomain",
            """
            SELECT ?id ?domain_id ?label {
                ?iri a ecv:ECV-subdomain ; skos:broader ?domain ; rdfs:label ?label .
                ?domain a ecv:ECV-domain .
                BIND(STRAFTER(STR(?iri), STR(ecv:)) AS ?id)
                BIND(STRAFTER(STR(?domain), STR(ecv:)) AS ?domain_id)
            } ORDER BY ?id""",
        )

        emit_csv(
            "variable",
            """
            SELECT ?id ?subdomain_id ?label ?definition {
                ?iri a ecv:ECV-variable ; skos:broader ?subdomain ; rdfs:label ?label .
                ?subdomain a ecv:ECV-subdomain .
                OPTIONAL { ?iri skos:definition ?definition }
                BIND(STRAFTER(STR(?iri), STR(ecv:)) AS ?id)
                BIND(STRAFTER(STR(?subdomain), STR(ecv:)) AS ?subdomain_id)
            } ORDER BY ?id
        """,
        )

        emit_csv(
            "product",
            """
            SELECT DISTINCT ?id ?label ?definition ?note ?unit_note {
                ?iri a ecv:ECV-product ; rdfs:label ?label ; skos:definition ?definition
                OPTIONAL { ?iri skos:note ?note FILTER(!STRSTARTS(?note, "Unit: ")) }
                OPTIONAL { ?iri skos:note ?n FILTER(STRSTARTS(?n, "Unit: ")) BIND(STRAFTER(?n, "Unit: ") AS ?unit_note)}
                BIND(STRAFTER(STR(?iri), STR(ecv:)) AS ?id)
            } ORDER BY ?id""",
        )

        emit_csv(
            "product_variable",
            """
            SELECT ?product_id ?variable_id {
                ?iri a ecv:ECV-product ; ecv:isProductOf ?variable
                BIND(STRAFTER(STR(?iri), STR(ecv:)) AS ?product_id)
                BIND(STRAFTER(STR(?variable), STR(ecv:)) AS ?variable_id)
            } ORDER BY ?product_id ?variable_id""",
        )

        emit_csv(
            "product_unit",
            """
            SELECT DISTINCT ?product_id ?unit_id ?unit_ns {
                ?iri a ecv:ECV-product ; qudt:hasUnit ?unit
                BIND(STRAFTER(STR(?iri), STR(ecv:)) AS ?product_id)
                BIND(REPLACE(REPLACE(REPLACE(STR(?unit),
                    STR(cunit:), "cunit:"),
                    STR(unit:), "unit:"),
                    STR(wmdr-unit:), "wmdr-unit:")
                AS ?uqn)
                BIND(STRAFTER(?uqn, ":") AS ?unit_id)
                BIND(STRBEFORE(?uqn, ":") AS ?unit_ns)
            } ORDER BY ?product_id ?unit_id ?unit_ns""",
        )


_ECV_SQL_TEMPLATE = Template("""
    CREATE TABLE ${prefix}domain (
        id VARCHAR NOT NULL,
        label VARCHAR NOT NULL,
        PRIMARY KEY (id)
    );

    CREATE TABLE ${prefix}subdomain (
        id VARCHAR NOT NULL,
        domain_id VARCHAR NOT NULL,
        label VARCHAR NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY (domain_id) REFERENCES ${prefix}domain(id)
    );

    CREATE TABLE ${prefix}variable (
        id VARCHAR NOT NULL,
        subdomain_id VARCHAR NOT NULL,
        label VARCHAR NOT NULL,
        definition VARCHAR,
        PRIMARY KEY (id),
        FOREIGN KEY (subdomain_id) REFERENCES ${prefix}subdomain(id)
    );

    CREATE TABLE ${prefix}product (
        id VARCHAR NOT NULL,
        label VARCHAR NOT NULL,
        definition VARCHAR,
        note VARCHAR,
        unit_note VARCHAR,
        PRIMARY KEY (id)
    );

    CREATE TABLE ${prefix}product_unit (
        product_id VARCHAR NOT NULL,
        unit_id VARCHAR NOT NULL,
        unit_ns VARCHAR NOT NULL,
        PRIMARY KEY (product_id, unit_id, unit_ns),
        FOREIGN KEY (product_id) REFERENCES ${prefix}product(id)
    );

    CREATE TABLE ${prefix}product_variable (
        product_id VARCHAR NOT NULL,
        variable_id VARCHAR NOT NULL,
        PRIMARY KEY (product_id, variable_id),
        FOREIGN KEY (product_id) REFERENCES ${prefix}product(id)
    );
""")


_ECV_OBDA_TEMPLATE = Template("""
    [PrefixDeclaration]
    cunit:      http://www.semanticweb.org/crima/crima-unit#
    ecv:        http://www.semanticweb.org/crima/crima-ecv#
    owl:        http://www.w3.org/2002/07/owl#
    qudt:       http://qudt.org/schema/qudt#
    rdfs:       http://www.w3.org/2000/01/rdf-schema#
    skos:       http://www.w3.org/2004/02/skos/core#
    unit:       http://qudt.org/vocab/unit/
    vann:       http://purl.org/vocab/vann/
    voaf:       http://purl.org/vocommons/voaf#
    wmdr-unit:  http://codes.wmo.int/wmdr/unit/

    [MappingDeclaration] @collection [[

    mappingId   ${prefix}static
    target      ecv:essential-climate-variables-system a ecv:EssentialClimaticVariables ;
                    rdfs:label "essential climate variables system"@en .
                <http://www.semanticweb.org/crima/crima-ecv-data#> a owl:Ontology ;
                    vann:preferredNamespacePrefix "ecv" ;
                    vann:preferredNamespaceUri "http://www.semanticweb.org/crima/crima-ecv#"^^xsd:anyURI ;
                    voaf:metadataVoc <http://purl.org/vocab/vann/> , <http://purl.org/vocommons/voaf> ;
                    voaf:reliesOn
                        <http://codes.wmo.int/wmdr/unit/> ,
                        <http://qudt.org/schema/qudt> ,
                        <http://qudt.org/vocab/unit> ,
                        <http://www.semanticweb.org/crima/crima-ecv#> ,
                        <http://www.semanticweb.org/crima/crima-unit#> ,
                        <http://www.w3.org/2004/02/skos/core> ;
                    owl:imports
                        <http://codes.wmo.int/wmdr/unit/> ,
                        <http://qudt.org/schema/qudt> ,
                        <http://qudt.org/vocab/unit> ,
                        <http://www.semanticweb.org/crima/crima-ecv#> ,
                        <http://www.semanticweb.org/crima/crima-unit#> ,
                        <http://www.w3.org/2004/02/skos/core> .
    source      SELECT 1

    mappingId   ${prefix}domain
    target      ecv:{id} a ecv:ECV-domain ;
                    rdfs:label "{label}"@en .
    source      SELECT * FROM ${prefix}domain

    mappingId   ${prefix}subdomain
    target      ecv:{id} a ecv:ECV-subdomain ;
                    skos:broader ecv:{domain_id} ;
                    rdfs:label "{label}"@en .
    source      SELECT * FROM ${prefix}subdomain

    mappingId   ${prefix}variable
    target      ecv:{id} a ecv:ECV-variable ;
                    skos:broader ecv:{subdomain_id} ;
                    rdfs:label "{label}"@en ;
                    skos:definition "{definition}"@en .
    source      SELECT * FROM ${prefix}variable

    mappingId   ${prefix}product
    target      ecv:{id} a ecv:ECV-product ;
                    rdfs:label "{label}"@en ;
                    skos:definition "{definition}"@en ;
                    skos:note "{note}"@en .
    source      SELECT * FROM ${prefix}product

    mappingId   ${prefix}product_unit_note
    target      ecv:{id} skos:note "{unit_note}"@en .
    source      SELECT id, CONCAT('Unit: ', unit_note) AS unit_note
                FROM ${prefix}product
                WHERE unit_note IS NOT NULL

    mappingId   ${prefix}product_variable
    target      ecv:{product_id} ecv:isProductOf ecv:{variable_id} .
    source      SELECT * FROM ${prefix}product_variable

    mappingId   ${prefix}product_unit_cunit
    target      ecv:{product_id} qudt:hasUnit cunit:{unit_id} .
    source      SELECT * FROM ${prefix}product_unit WHERE unit_ns = 'cunit'

    mappingId   ${prefix}product_unit_unit
    target      ecv:{product_id} qudt:hasUnit unit:{unit_id} .
    source      SELECT * FROM ${prefix}product_unit WHERE unit_ns = 'unit'

    mappingId   ${prefix}product_unit_wmdr_unit
    target      ecv:{product_id} qudt:hasUnit wmdr-unit:{unit_id} .
    source      SELECT * FROM ${prefix}product_unit WHERE unit_ns = 'wmdr-unit'

    ]]
""")
