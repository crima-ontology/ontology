import logging
import shutil
from pathlib import Path
from textwrap import dedent
from time import time
from typing import Any, Self

import click
import markdown
from bs4 import BeautifulSoup, NavigableString
from mkdocs.config import config_options
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import BasePlugin
from pylode.profiles.ontpub import OntPub
from rdflib import DCTERMS, OWL, RDF, RDFS, BNode, Graph, Literal, URIRef
from rdflib.namespace import NamespaceManager

from crima_ontology_tool.util import create_graph, rdf_read, rdf_write

_LOGGER = logging.getLogger(__name__)


@click.command(name="pylode")
@click.argument("inputs", metavar="INPUT_PATH...", nargs=-1)
@click.option("-o", "--output-dir", default=".", help="parent output directory where to emit documentation")
@click.option("-p", "--prefixes-from", help="optionally reuse prefixes from supplied file")
def cli_pylode(inputs: list[str], output_dir: str = ".", prefixes_from: str | None = None) -> None:
    """
    Generate publishable artifacts for ontology modules, including Markdown documentation via PyLode.

    For each input RDF file, a directory under 'output-dir' is created and is populated with the RDF file in different
    RDF formats (.ttl, .rdf, .nt, .json). If the file contains exactly one owl:Ontology, an additional '.md' markdown
    file is emitted containing documentation for classes and properties generated via PyLode + markdown diagrams. This
    .md file is meant to be used in input to mkdocs to build a static website to document the ontology modules.
    """
    generate_artifacts([Path(f) for f in inputs], Path(output_dir), Path(prefixes_from) if prefixes_from else None)


class PylodePlugin(BasePlugin):
    """
    Generate PyLode documentation for MkDocs.

    The plugin operates on a configured set of ontology RDF files in input. For each file, it copies its RDF content
    in different formats in an output directory named after the input file, also generating a markdown page in the
    same directory using PyLode. These files are then picked up by mkdocs when building the documentation website.

    Configuration properties:
    * input: a list of strings, each being the path of an RDF file relative to the directory with mkdocs.yml
    * output: the path (relative to mkdocs.yml) of a parent output directory where to place all outputs
    * prefixes: the path (relative to mkdocs.yml) of an optional RDF file whose prefixes has to be used for all outputs
    """

    # Plugin configuration properties and their expected types
    config_scheme = (
        ("input", config_options.Type(list, default=[])),
        ("output", config_options.Type(str, default="modules")),
        ("prefixes", config_options.Type(str)),
    )

    def on_pre_build(self, config: MkDocsConfig) -> None:
        # Callback method invoked by mkdocs prior to generating documentation
        root_dir = Path(config["config_file_path"]).parent
        docs_dir = Path(config["docs_dir"])
        output_parent_dir = docs_dir / config.get("output", "modules")
        input_files = [root_dir / f for f in self.config.get("input", [])]
        prefixes_file = root_dir / self.config["prefixes"] if self.config.get("prefixes") else None
        generate_artifacts(input_files, output_parent_dir, prefixes_file)


def generate_artifacts(input_files: list[Path], output_parent_dir: Path, prefixes_file: Path | None = None) -> None:

    # Raise an error (before possibly overwriting files) if any of the specified input files is missing
    for input_file in input_files:
        if not input_file.exists():
            msg = f"File {input_file} does not exist"
            raise ValueError(msg)

    # Load prefixes if possible
    ns_manager: NamespaceManager = None
    if prefixes_file:
        graph = create_graph()
        rdf_read(graph, str(prefixes_file))
        ns_manager = graph.namespace_manager

    # Process one RDF input file at a time
    for input_file in input_files:
        generate_artifact(input_file, output_parent_dir, ns_manager)


def generate_artifact(input_file: Path, output_parent_dir: Path, ns_manager: NamespaceManager | None = None) -> None:

    # Derive module name from input filename except extension, and determine consequently the output directory
    name = input_file.name.split(".")[0]
    output_dir = output_parent_dir / name

    # Skip generation if all output files are present with a timestamp more recent than the input file one
    input_ts = input_file.stat().st_mtime
    output_ts = time()
    for ext in (".ttl", ".nt", ".rdf", ".json", ".md"):
        output_file = output_dir / (name + ext)
        output_ts = min(output_ts, output_file.stat().st_mtime if output_file.exists() else -1)
    if output_ts >= input_ts:
        return

    # (Re-)Create the output directory where to put artifacts produced for the input file
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Read the RDF content of the input file
    graph = create_graph()
    rdf_read(graph, str(input_file))

    # Replace prefix-namespace bindings if specified
    if ns_manager:
        graph.namespace_manager.reset()
        for prefix, ns in ns_manager.namespaces():
            graph.bind(prefix, ns)

    # Skip file with warning in case it contains no / multiple ontologies
    ontologies = list(graph.subjects(RDF.type, OWL.Ontology))
    if not ontologies or len(ontologies) > 1:
        _LOGGER.warning("File %s: %d ontology/ies in the file, ignoring", input_file, len(ontologies))
        return

    # Emit RDF content in multiple formats
    for ext in (".ttl", ".nt", ".rdf", ".json"):
        rdf_write(graph, str(output_dir / (name + ext)), canonicalize_ntriples=False)

    # Emit markdown documentation
    markdown = generate_markdown(graph, ontologies[0], name)
    with (output_dir / (name + ".md")).open("wt") as f:
        f.write(markdown)


def generate_markdown(graph: Graph, ontology_iri: URIRef, name: str) -> str:

    # Derive #-based ontology namespace for URI, for assigning anchors in the page
    ontology_ns = str(ontology_iri) + "#" if not ontology_iri.endswith("#") else str(ontology_iri)

    # Generate HTML using pylode
    html = generate_pylode(graph, ontology_iri, name)

    # Parse HTML using BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # Start emitting markdown one block at a time, beginning with header
    title = soup.find("h1").text
    markdown: list[str] = []
    markdown.append(
        dedent(f"""
        ---
        title: {title}
        description: Generated documentation for module {name}
        icon: material/graph
        ---

        # {title}

        <div class="pylode">
            <a class="md-button" target="_blank" href="{name}.ttl">ttl</a>
            <a class="md-button" target="_blank" href="{name}.rdf">rdf</a>
            <a class="md-button" target="_blank" href="{name}.nt">nt</a>
            <a class="md-button" target="_blank" href="{name}.json">json</a>
            &nbsp;
            <a class="md-button" target="_blank" href="https://service.tib.eu/webvowl/#iri={ontology_iri}">WebVOWL</a>
        </div>
        """).strip()
    )

    # Append all sections generated by pylode, converting headers to markdown
    for h2 in soup.find_all("h2"):
        div = h2.find_parent("div")
        children = list(div.find_all("dl", recursive=False)) + [
            e for e in div.find_all("div", recursive=False) if e.find("code").text.startswith(ontology_ns)
        ]
        if not children:
            continue
        markdown.append(f"## {h2.text}")
        for child in children:
            wrapper = soup.new_tag("div", attrs={"class": "pylode"})
            if child.name != "div":
                markdown.append(child.wrap(wrapper).prettify().strip())
            else:
                title = "".join(t for t in child.find("h3").contents if isinstance(t, NavigableString)).strip()
                child = child.find("table")  # noqa: PLW2901
                iri: str = child.find("code").text
                id = iri[len(ontology_ns) :] if iri.startswith(ontology_ns) else None
                markdown.append(f"### {title}" + (" {#" + id + "}" if id else ""))
                mermaid = generate_mermaid(graph, URIRef(iri))
                chtml = child.wrap(wrapper).prettify().strip()
                if mermaid:
                    chtml = chtml.replace(
                        " </table>",
                        f"  <tr>\n   <th></th>\n   <td>\n```mermaid\n{mermaid}\n```\n   </td>\n  </tr>\n </table>",
                    )
                markdown.append(chtml)

    # Concatenate markdown blocks into the result string
    return "\n\n".join(markdown)


def generate_pylode(graph: Graph, ontology_iri: URIRef, name: str) -> str:

    # PyLode is currently unable to render restrictions where the object on owl:onProperty, owl:someValuesFrom,
    # owl:allValuesFrom is a BNode (i.e., an inverse property, or a complex concept expression). PyLode will try
    # to render these BNodes as if they are property/class IRIs, with the result that a None:<bnode-id> string
    # is rendered. Therefore, we filter these restrictions out for the time being. A fix should go to pylode/utils.py
    # in function rdf_obj_html > _rdf_obj_single_html > _restriction_html (should call _bn_html recursively instead
    # of _hyperlink_html, or something like that)
    excluded_restrictions = {
        t[0]
        for p in (OWL.onProperty, OWL.someValuesFrom, OWL.allValuesFrom)
        for t in graph.triples((None, p, None))
        if isinstance(t[2], BNode)
    }

    # Patch the RDF graph by adding a default dcterms:title (using module name) if missing and by prepending a
    # whitespace to every literal starting with 'http', to avoid PyLode rendering the whole literal as a link
    # (if there is a URL, it will still be rendered as link by pymdownx.magiclink)
    pylode_graph = create_graph(namespaces_from=graph)
    for s, p, o in graph:
        if s not in excluded_restrictions:
            pylode_graph.add((s, p, Literal(" " + o) if isinstance(o, Literal) and o.startswith("http") else o))
    if (ontology_iri, DCTERMS.title, None) not in pylode_graph:
        pylode_graph.add((ontology_iri, DCTERMS.title, Literal(name)))

    # Setup monkey patching of NamespaceManager.compute_qname to avoid failing in case a QName cannot be derived
    compute_qname_original = NamespaceManager.compute_qname

    def compute_qname_patched(self: Self, uri: str, generate: bool = True) -> tuple[str, URIRef, str]:  # noqa: FBT001, FBT002
        try:
            return compute_qname_original(self, uri, generate)
        except ValueError:
            return (None, uri, str(uri))

    # Setup monkey patching of markdown.markdown to include by default extension pymdownx.magiclink
    markdown_original = markdown.markdown

    def markdown_patched(*args: Any, **kwargs: Any) -> str:
        extensions = list(kwargs.get("extensions", []))
        for extension in ("extra", "sane_lists", "pymdownx.magiclink", "pymdownx.inlinehilite"):
            if extension not in extensions:
                extensions.append(extension)
        kwargs["extensions"] = extensions
        return markdown_original(*args, **kwargs)

    try:
        # Apply monkey patching
        NamespaceManager.compute_qname = compute_qname_patched
        markdown.markdown = markdown_patched

        # Invoke PyLode, returning generated HTML
        od = OntPub(ontology=pylode_graph, sort_subjects=True)
        return od.make_html(include_css=True)

    finally:
        # Ensure to undo monkey patching
        NamespaceManager.compute_qname = compute_qname_original
        markdown.markdown = markdown_original


def generate_mermaid(graph: Graph, iri: URIRef) -> str | None:

    # Identify super/sub-classes, aborting if there is none (diagram would be empty / one node)
    superclasses = [c for c in graph.objects(iri, RDFS.subClassOf) if isinstance(c, URIRef)]
    subclasses = [c for c in graph.subjects(RDFS.subClassOf, iri) if isinstance(c, URIRef)]
    if not superclasses and not subclasses:
        return None

    # Start generating a flowchart diagram, starting from Mermaid config and flowchart directives
    mermaid = []
    mermaid.append(
        "%%{init: {"
        '"flowchart": {"nodeSpacing": 20, "rankSpacing": 50, "padding": 8}, '
        '"themeVariables": {"fontSize": "13px"}'
        "}}%%"
    )
    mermaid.append("flowchart RL")

    # Generate a flowchart node input class and its super/sub-classes, rendering them as links
    for c in [iri, *superclasses, *subclasses]:
        qname = graph.namespace_manager.qname(c)
        id = qname.replace(":", "_")
        mermaid.append(f'    {id}["{qname if c != iri else "<b>" + qname + "</b>"}"]')
        mermaid.append(f'    click {id} href "{c!s}"')

    # Generate rdfs:subClass edges
    for child, parent in [(iri, c) for c in superclasses] + [(c, iri) for c in subclasses]:
        child_id = graph.namespace_manager.qname(child).replace(":", "_")
        parent_id = graph.namespace_manager.qname(parent).replace(":", "_")
        mermaid.append(f"    {child_id} -->|rdfs:subClassOf| {parent_id}")

    # Concatenate all lines and return resulting Mermaid code
    return "\n".join(mermaid)
