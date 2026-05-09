# Utility Scripts for Maintaining the CRIMA Ontology and Mappings

This directory contains the `crima-vkg-tool` Python tool for carrying out various ontology maintenance tasks. It comes as a regular Python project (see `pyproject.toml`) depending on external libraries (e.g., rdflib), and is meant to be installed in a *virtual environment*. The most straightforward way to do that is reported next, although any Python tools for managing virtual environments and installing packages can be used:
```bash
cd scripts                        # move to the scripts/ directory, if not already there
python3 -m venv .venv             # create a virtual environment in folder .venv (name it whatever you like)
source .venv/bin/activate         # activate the environment
pip install -U pip                # upgrade pip
pip install -e .                  # install the 'crima-vkg-tool' project in editable mode, along with its dependencies
crima-vkg-tool --help             # test whether scripts work (work in any directory as long as environment is activated)
```

Once done, run `deactivate` to deactivate the environment, or simply close the shell. To reactivate, enter the scripts directory and run again `source .venv/bin/activate`. To get rid of the environment, deactivate it and delete the created `.venv` directory. Any update to script sources (e.g., resulting from local edits / `git pull` actions) will be immediately effective due to install in editable mode. The tool and the installation procedure listed above should work also on Windows, though development and testing are mostly done in Linux.

Some reference documentation about using the tool is available through command line help (run `crima-vkg-toll <command> --help` for command specific help):
```
Usage: crima-vkg-tool [OPTIONS] COMMAND [ARGS]...

  Utility tool to maintain CRIMA ontology and mapping.

Options:
  -v, --verbose  log debug information to stderr
  --help         Show this message and exit.

Commands:
  catalog   Generate catalog-v001.xml files for use in Protégé / OWL API.
  cclc      Utilities related to CRIMA CORINE Land Cover (CCLC) Abox data.
  download  Download external vocabularies referenced by the CRIMA ontology into the directory specified.
  ecv       Utilities related to Essential Climate Variables (ECV) Abox data.
  hip       Utilities related to HIP Abox data.
  merge     Merge multiple OWL/RDF files into a single one.
  mermaid   Generate a Markdown + Mermaid diagram of ontology voaf:reliesOn relations.
  sanitize  Sanitize RDF data from one or more files, writing sanitized RDF output to a specified file.
  split     Split merged RDF data about multiple ontologies into multiple output RDF files, one per ontology.
```

Next, we list the main tasks provided by scripts. All the listed commands are assumed to be executed in the `wp2/vkg/` directory.

## Merge Modules into a Single File

The following commands merge all modules and external vocabularies (either fragments or full versions) into a self-contained file `ontology.ttl`, optionally dropping all `owl:imports` (via option -s) and retaining only `rdf:langString` literals with language `en`, `it` or `de`:
```bash
crima-vkg-tool merge -o ontology.ttl ontology/crima.ttl ontology/modules/*.ttl ontology/imports/fragments/*.ttl                 # use fragments
crima-vkg-tool merge -o ontology.ttl ontology/crima.ttl ontology/modules/*.ttl ontology/imports/fragments/*.ttl -l en,it,de -s  # use fragments, filter by language, remove owl:imports
crima-vkg-tool merge -o ontology.ttl ontology/crima.ttl ontology/modules/*.ttl ontology/imports/full/*.ttl -l en,it,de -s       # use full ext. vocabularies, filter and remove owl:imports
```

## Split a Single Files into Modules

The following command splits a single merged file, such as the `ontology.ttl` build previously (with fragments, no filtering or `owl:imports` removal), into modules / external vocabularies, based on additional module metadata in `ontology/testing/metadata.ttl`. The generated `leftover.nt` file contains statements that could not be allocated to modules / vocabularies according to employed metadata. The produced files correspond to those prior to merging, with minor changes due to transitory module `ex:` that lacks proper metadata in `ontology/testing/metadata.ttl`, and whose content ends up partly scattered in other files.
```bash
crima-vkg-tool split -l leftover.nt -o output-dir/ ontology.ttl ontology/testing/metadata.ttl
```

## Downloading External Vocabularies

The following command will download *missing* external vocabularies under `ontology/imports/full`, skipping download if the target file already exists (delete it to re-download):
```bash
crima-vkg-tool download -o ontology/imports/full/
```

## Generating Protégé Catalog Files

The following commands will create/overwrite the `catalog-v001.xml` files located in folders `ontology/`, `ontology/modules/`, `ontology/imports/fragments/`, `ontology/imports/full/`, `ontology/test/full`, based on the ontology modules and external vocabulary (full/fragments) actually present:
```bash
( cd ontology; crima-vkg-tool catalog -o catalog-v001.xml crima.ttl modules/*.ttl imports/fragments/*.ttl )
( cd ontology/modules; crima-vkg-tool catalog -o catalog-v001.xml *.ttl ../imports/fragments/*.ttl )
( cd ontology/imports/fragments; crima-vkg-tool catalog -o catalog-v001.xml *.ttl )
( cd ontology/imports/full; crima-vkg-tool catalog -o catalog-v001.xml *.ttl )
( cd ontology/testing/full; crima-vkg-tool catalog -o catalog-v001.xml crima.ttl ../../modules/*.ttl ../../imports/full/*.ttl )
```

## Generating Mermaid Diagram

The following command will print to `stdout` the Mermaid source code for the diagram showing module dependencies (`voaf:*` relations), which can then be included in markdown files (as the main `README.md`) for display:
```bash
crima-vkg-tool mermaid \
    -e "sg_modules -------- sg_imports_fragments" \
    -e "linkStyle 0 stroke-width:0px" \
    ontology/crima.ttl \
    ontology/modules/*.ttl \
    ontology/imports/fragments/*.ttl \
    ontology/testing/metadata.ttl
```

## Dealing with ECV Data

The following command will create a ZIP `unibz_ecv.zip` containing equivalent CSV files (one per table, prefixed by `unibz_ecv_`), a SQL schema, and OBDA mapping for ECV ABox data residing in `ontology/modules/ecv-data.ttl`:
```bash
crima-vkg-tool ecv csv -o unibz_ecv.zip -p unibz_ecv_ ontology/modules/ecv-data.ttl
```

## Dealing with HIP Data

The following command will crawl HIP pages starting from https://www.preventionweb.net/drr-glossary/hips (unless specified otherwise), collecting RDF data embedded as JSON-LD / RDFa and storing it as-is (including irrelevant triples, noisy triples) into a file `hip-crawl.ttl`.
```bash
crima-vkg-tool hip crawl -o hip-crawl.ttl
```

The following command will reshape crawled HIP data into the format used in CRIMA, also applying sanitization to handle special/control characters in raw HIP data, resulting in the content of file at `ontology/modules/hip-data.ttl`:
```bash
crima-vkg-tool hip reshape hip-crawl.ttl | crima-vkg-tool sanitize -o ontology/modules/hip-data.ttl -
```

The following command will create a ZIP `unibz_hip.zip` containing equivalent CSV files (one per table, prefixed by `unibz_hip_`), a SQL schema, and OBDA mapping for reshaped HIP ABox data residing in `ontology/modules/hip-data.ttl`:
```bash
crima-vkg-tool hip csv -o unibz_hip.zip -p unibz_hip_ ontology/modules/hip-data.ttl
```

## Dealing with CCLC Data

The following command will create a ZIP `unibz_cclc.zip` containing equivalent CSV files (one table, prefixed by `unibz_cclc_`), a SQL schema, and OBDA mapping for CCLC ABox data residing in `ontology/modules/cclc-data.ttl`:
```bash
crima-vkg-tool cclc csv -o unibz_cclc.zip -p unibz_cclc_ ontology/modules/cclc-data.ttl
```

## Sanitize an RDF/OWL File

The following command will read RDF/OWL data, sanitize literals by normalizing/removing invisible unicode characters, and optionally apply <prefix, namespace> bindings from another file:
```bash
crima-vkg-tool sanitize -p ontology/testing/prefixes.ttl -o crima_sanitized.ttl ontology/crima.ttl
```
