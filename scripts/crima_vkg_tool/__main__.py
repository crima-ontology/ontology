import logging

import click

from crima_vkg_tool.catalog import cli_catalog
from crima_vkg_tool.download import cli_download
from crima_vkg_tool.ecv import cli_ecv
from crima_vkg_tool.merge import cli_merge
from crima_vkg_tool.mermaid import cli_mermaid
from crima_vkg_tool.sanitize import cli_sanitize
from crima_vkg_tool.split import cli_split


@click.group(context_settings={"show_default": True, "max_content_width": 120})
@click.option("-v", "--verbose", is_flag=True, help="log debug information to stderr")
def cli(*, verbose: bool = False) -> None:
    """Utility tool to maintain CRIMA ontology and mapping."""  # noqa: D401
    logging.basicConfig(format="%(asctime)s (%(levelname).1s) %(message)s", datefmt="%H:%M:%S")
    logging.getLogger().setLevel(logging.DEBUG if verbose else logging.INFO)


cli.add_command(cli_catalog)
cli.add_command(cli_download)
cli.add_command(cli_ecv)
cli.add_command(cli_merge)
cli.add_command(cli_mermaid)
cli.add_command(cli_sanitize)
cli.add_command(cli_split)


# TODO: in merge command, consider materializing sesame/sp triples
# TODO: in mermaid command, do not rely on mod:hasSerialization metadata
