
# Documentation Sources and Assets

This directory contains assets (images, CSS, etc., under `assets`) and Markdown sources (other folders and files) used to generate the static website at https://crima-ontology.github.io/.


## How to Generate Website Content

The generation workflow is centred around [MkDocs](https://www.mkdocs.org/). Specifically it employs:
- [Materials for MkDocs](https://squidfunk.github.io/mkdocs-material/), as the documentation theme and framework over MkDocs;
- [mike](https://github.com/jimporter/mike), as MkDocs plugin and managing tool to handle versioning;
- [a custom `pylode` plugin](`../scripts`), part of the Python scripts in this repository, to generate Markdown / HTML documentation for ontology modules wrapping [pyLODE](https://github.com/RDFLib/pyLODE).

To setup these components, just follow the [instructions](../scripts/README.md) for setting up a Python virtual environment for the `crima-ontology-tool` scripts. Then, to generate the documentation, activate the virtual environment and run the following commands from the root repository directory (the one containing `scripts/` and `docs/`):
```bash
mkdocs build -c
```
This will generate the website content under unversioned directory `site/`. Just open `site/index.html` in a browser to check it. Note that the command will also generate publishable artifacts for the ontology under unversioned directory `docs/modules`, with a sub-directory for each module. These are staging files that are updated if needed following changes to ontology modules. Feel free to delete both directories `site/` and `docs/modules`.


## How to Deploy the Website

Deployment consists in committing and pushing the generated website files to repository [crima-ontology.github.io](github.com/crima-ontology/crima-ontology.github.io), under a subdirectory `docs/<VERSION>` specific to the version of the CRIMA ontology being published.

This process has to be done using the [`mike`](https://github.com/jimporter/mike) tool. It takes care of generating the documentation by running `mkdocs`, to commit it to a local `gh-pages` branch, and to push this branch to the remote repository, also generating and pushing a [version metadata file](https://github.com/crima-ontology/crima-ontology.github.io/blob/gh-pages/docs/versions.json) that is used by the version selection dropdown in the website.

The deploy workflow is the following (all commands prior to the `mike` ones have to be done the first time only)
```bash
# Clone the 'ontology' repository, as following commands have to be issued in a local git-managed repository
git clone git@github.com:crima-ontology/ontology.git
cd crima-ontology

# Add the crima-ontology.github.io repository as remote, and fetch branches' information
git remote add mkdocs git@github.com:crima-ontology/crima-ontology.github.io.git
git fetch -a mkdocs

# Call mike to generate documentation and publish it under version 'latest' (change if needed)
mike deploy --push --remote mkdocs latest

# Call mike to set version 'latest' (change if needed) as the default one served if a user access https://crima-ontology.github.io/
mike set-default --push --remote mkdocs latest
```

The `mike` operates on a local `gh-pages` branch first, before pushing its content to the crima-ontology.github.io repository. This local branch can be safely deleted (`git branch -d gh-pages`), and this should be done in case `mike` fails or omits (if `--push` is not passed) to push changes, and repeating the `mike` command results in `warning: nothing changed in commit`.

After deploying, a GitHub action named [`pages build and deployment`](https://github.com/crima-ontology/crima-ontology.github.io) managed by GitHub as part of the GitHub pages service will process the pushed content and update the website, so changes will be visible only after this action completes. It's recommended to check https://crima-ontology.github.io/ to ensure everything is fine after the deploy. Any issue can be also fixed manually be editing the content of branch `gh-pages` of the remote repository.


## How to Modify the Website Content

The pages forming the generated website, and their online paths, are configured in [`mkdocs.yml`](../mkdocs.yml), mainly under `nav`. Please refer to the documentation of [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) or [MkDocs](https://www.mkdocs.org/) itself (or any of the many tutorials / LLMs online) for further information.

Page contents are in Markdown, with the possibility to embed HTML in it (and to embed Markdown in the embedded HTML too). Pages and other files under `docs/modules` are generated from ontology files: do not edit them directly, but instead edit/enrich the annotations (e.g., `rdfs:label`, `dcterms:description`, ...) in the ontology files. The properties recognized by pyLODE are listed [here](https://github.com/RDFLib/pyLODE/blob/master/pylode/rdf_elements.py). See also this [guide](https://dgarijo.github.io/Widoco/doc/bestPractices/index-en.html) about common use ontology annotations.

Only pages selected in `mkdocs.yml` will form part of the navigation menu of the website. However, note that all files under `docs/` are by default processed by `mkdocs` and the corresponding output (e.g., HTML version of a Markdown file) included in the generated website, even if not reachable from the navigation menu. To exclude a file, list it under `exclude_docs` in `mkdocs.yml`.
