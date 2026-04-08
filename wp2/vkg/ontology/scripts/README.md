# Utility Scripts for Maintaining the CRIMA Ontology

This directory contains Python scripts to carry out various ontology maintenance tasks. They depend on external libraries (e.g., rdflib) that need to be installed in a *virtual environment*:
```bash
cd scripts                        # move to the scripts/ directory, if not already there
python3 -m venv .venv             # create a virtual environment in folder .venv (name it whatever you like)
source .venv/bin/activate         # activate the environment
pip install -U pip                # upgrade pip
pip install -r requirements.txt   # install all libraries listed in file requirements.txt
./helper --help                   # test whether scripts work (no error raised and the help message should be displayed)
```

Once done, run `deactivate` to deactivate the environment, or simply close the shell. To reactivate, enter the scripts directory and run again `source .venv/bin/activate`. To get rid of the environment, deactivate it and delete the created `.venv` directory.

We list next the main tasks provided by scripts. All the listed commands have to be executed in the root ontology directory, i.e., the one containing `crima.ttl`.

## Merge Modules into a Single File

The following commands merge all modules and external vocabularies (either fragments or full versions) into a self-contained file `ontology.ttl`, dropping all `owl:imports` (via option -s) and retaining only `rdf:langString` literals with language `en`, `it` or `de`:
```bash
scripts/helper merge -l en,it,de -s -o ontology.ttl crima.ttl modules/*.ttl imports/fragments/*.ttl  # to use fragments of external vocabularies
scripts/helper merge -l en,it,de -s -o ontology.ttl crima.ttl modules/*.ttl imports/full/*.ttl       # to use full external vocabularies
```

## Downloading External Vocabularies

The following command will download *missing* external vocabularies under `imports/full`, skipping download if the target file already exists (delete it to re-download):
```bash
scripts/helper download -o imports/full/
```

## Generating Protégé Catalog Files

The following commands will create/overwrite the `catalog-v001.xml` files located in folders `/`, `modules/`, `imports/fragments/`, `imports/full/`, `test/full`, based on the ontology modules and external vocabulary (full/fragments) actually present:
```bash
scripts/helper catalog -o catalog-v001.xml crima.ttl modules/*.ttl imports/fragments/*.ttl
( cd modules; ../scripts/helper catalog -o catalog-v001.xml *.ttl ../imports/fragments/*.ttl )
( cd imports/fragments; ../../scripts/helper catalog -o catalog-v001.xml *.ttl )
( cd imports/full; ../../scripts/helper catalog -o catalog-v001.xml *.ttl )
( cd testing/full; ../../scripts/helper catalog -o catalog-v001.xml crima.ttl ../../modules/*.ttl ../../imports/full/*.ttl )
```

## Generating Mermaid Diagram

The following command will print to `stdout` the Mermaid source code for the diagram showing module dependencies (`voaf:*` relations), which can then be included in markdown files (as the main `README.md`) for display:
```bash
scripts/helper mermaid -e 'sg_modules --------- sg_imports_fragments' -e 'linkStyle 0 stroke-width:0px' crima.ttl modules/*.ttl imports/fragments/*.ttl scripts/metadata.ttl
```

## Additional Commands

Run the following to list all supported commands and their options:
```bash
scripts/helper --help           # show general options and list all supported commands
scripts/helper sanitize --help  # show help for a specific command (here: 'sanitize')
```