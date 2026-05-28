import click
from rdflib import OWL, Literal

from crima_ontology_tool.util import create_graph, rdf_read, rdf_write


@click.command(name="merge")
@click.argument("inputs", metavar="INPUT_FILE...", nargs=-1)
@click.option("-o", "--output-file", default="-", help="output merged file ('-' for stdout, the default)")
@click.option(
    "-l",
    "--languages",
    multiple=True,
    help="the rdf:langString languages to preserve in the merged file (e.g., 'en,it,de')",
)
@click.option("-s", "--simplify", is_flag=True, help="remove owl:imports statements")
def cli_merge(
    inputs: list[str], *, output_file: str = "-", languages: list[str] | None = None, simplify: bool = False
) -> None:
    """Merge multiple OWL/RDF files into a single one."""
    graph = create_graph()
    for input in inputs or [".ttl:-"]:
        rdf_read(graph, input)

    if languages:
        languages = {lang for lang_list in languages for lang in lang_list.split(",")}
        for triple in list(graph):
            o = triple[2]
            if isinstance(o, Literal) and o.language and o.language not in languages:
                graph.remove(triple)

    if simplify:
        graph.remove((None, OWL.imports, None))

    rdf_write(graph, output_file)
