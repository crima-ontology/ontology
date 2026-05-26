---
title: CRIMA Ontology
description: Introduction to the CRIMA ontology.
icon: material/home
---


# CRIMA Ontology

<p style="margin-top: -2rem; margin-bottom: 2rem; font-size: 1rem; font-style: italic; font-weight: lighter; color: var(--md-default-fg-color--light);">
    The Ontology for Evidence-based Management of Climate Risks
</p>


**CRIMA** is a modular domain ontology that formalises key concepts related to *climate risk* (e.g., hazard, exposure, vulnerability).
It enables the interlinking of:

1. qualitative domain knowledge captured through [*Impact Chains*](https://link.springer.com/chapter/10.1007/978-3-030-86211-4_25),
2. historical and simulated (quantitative) data, such as exposed assets and climatic events, and
3. established terminologies for risk-related concepts, some of which are provided as modules within CRIMA itself.

CRIMA serves as the semantic backbone for Knowledge Graph systems in the climate risk domain, facilitating the integration of heterogeneous data sources and supporting more informed climate change adaptation and risk management decisions.


## Scope and Design Principles

The CRIMA ontology focuses on semantic interoperability for climate risk assessment and adaptation workflows.

The ontology:

- is formalised in **OWL 2 DL**, with supplementary **SWRL** rules documenting additional intended semantics
- supports the integration of heterogeneous datasets with conceptual risk models
- provides a modular semantic framework for representing climate risk knowledge
- reuses established Semantic Web standards and domain vocabularies whenever possible, including SKOS, OWL-Time, GeoSPARQL, SOSA/SSN, QUDT, DCTERMS, and BIBO
- avoids commitment to a single upper ontology

The ontology is not intended to:

- provide operational support for disaster emergency response
- prescribe specific risk assessment methodologies
- act as a data repository or data management platform


## Ontology Structure

CRIMA follows a modular architecture organised into thematic ontology modules.

The following diagram illustrates CRIMA modules (in green) along with reused third-party vocabularies (in gray) and the overall import structure.

<img src="assets/diagram.svg" alt="Ontology modules" width="750px"/>

The following CRIMA ontology modules are included:

| Category | Module(s) | Description |
|---|---|---|
| **Main** | [`ccore`](modules/ccore/ccore.md) | Core module providing a minimal, literature-grounded theory of climate risk to represent and link risk-related entities (e.g., hazards, impacts, exposures) in data and conceptual models |
|  | [`ctlo`](modules/ctlo/ctlo.md) | Top-level ontology notions (e.g., event, process, quality) without commitment to a specific upper ontology |
|  | [`ich`](modules/ich/ich.md) | Ontological representation of *Impact Chains* [🔗](https://link.springer.com/chapter/10.1007/978-3-030-86211-4_25) |
| **Terminology** | [`ecv`](modules/ecv/ecv.md) | *Essential Climate Variables* list with associated descriptions and units [🔗](https://oceanrep.geomar.de/id/eprint/57694/1/GCOS-245_2022_GCOS_ECVs_Requirements.pdf) |
|  | [`hip`](modules/hip/hip.md) | Hazard classification from the 2025 edition of the *Hazard Information Profiles (HIP)* [🔗](https://www.undrr.org/publication/documents-and-publications/hazard-information-profiles-hips-2025-version) |
|  | [`ar6-impact`](modules/ar6-impact/ar6-impact.md) | Classification of *Observed Impacts from Climate Change* [🔗](https://www.ipcc.ch/report/ar6/wg2/) |
|  | [`emdat`](modules/emdat/emdat.md) | EM-DAT disaster classification [🔗](https://council.science/wp-content/uploads/2019/12/Peril-Classification-and-Hazard-Glossary-1.pdf) |
|  | [`ar5-adapt`](modules/ar5-adapt/ar5-adapt.md) | IPCC AR5 Adaptation scheme [🔗](https://www.ipcc.ch/site/assets/uploads/2018/02/SYR_AR5_FINAL_full.pdf#page=43) |
|  | [`ar6-cid`](modules/ar6-cid/ar6-cid.md) | *Climatic Impact Drivers (CID)* types and categories [🔗](https://www.cambridge.org/core/books/climate-change-2021-the-physical-science-basis/415F29233B8BD19FB55F65E3DC67272B) |
|  | [`cunit`](modules/cunit/cunit.md) | Additional units complementing QUDT [🔗](https://qudt.org/) |
|  | [`cclc`](modules/cclc/cclc.md) | CORINE land cover nomenclature [🔗](https://land.copernicus.eu/en/technical-library/clc-illustrated-nomenclature-guidelines/@@download/file) |
| **Helper** | [`cbib`](modules/cbib/cbib.md) | Bibliography-related concepts aligned to BIBO [🔗](https://dcmi.github.io/bibo/) and DCTERMS [🔗](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/) |
|  | [`cplace`](modules/cplace/cplace.md) | Geospatial entity classes aligned to GeoSPARQL [🔗](https://www.ogc.org/standards/geosparql/), SOSA [🔗](https://www.w3.org/TR/vocab-ssn/) and DBpedia ontology [🔗](https://www.dbpedia.org/resources/ontology/)|
|  | [`crid`](modules/crid/crid.md) | Concepts and properties for established identification systems (e.g., ZIP codes) |


## License

The CRIMA ontology is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).


## Acknowledgements

This ontology has been developed within the *CRIMA project* (Evidence-based Management of Climate Risks), funded by the *European Regional Development Fund (FESR)*.

CRIMA aims to support evidence-based climate risk assessment by integrating Earth Observation data, scientific knowledge, and semantic technologies.

Project website: [crima.eurac.edu](https://crima.eurac.edu/)

<img src="assets/fesr_logos.png" alt="FESR logo" width="500px"/>
