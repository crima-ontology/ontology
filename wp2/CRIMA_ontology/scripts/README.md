# Utility Scripts for Maintaining the CRIMA Ontology

## Downloading External Vocabularies

From root ontology directory (the one containing `crima.ttl`), execute:
```bash
scripts/helper download -o imports/full/
```

## Generating Protégé Catalog Files

From root ontology directory (the one containing `crima.ttl`), execute:
```bash
scripts/helper catalog -o catalog-v001.xml crima.ttl modules/*.ttl imports/fragments/*.ttl
( cd modules; ../scripts/helper catalog -o catalog-v001.xml *.ttl ../imports/fragments/*.ttl )
( cd imports/fragments; ../../scripts/helper catalog -o catalog-v001.xml *.ttl )
( cd imports/full; ../../scripts/helper catalog -o catalog-v001.xml *.ttl )
( cd testing/full; ../../scripts/helper catalog -o catalog-v001.xml crima.ttl ../../modules/*.ttl ../../imports/full/*.ttl )
```

## Generating Mermaid Diagram

From root ontology directory (the one containing `crima.ttl`), execute:
```bash
scripts/helper mermaid -e 'sg_modules --------- sg_imports_fragments' -e 'linkStyle 0 stroke-width:0px' crima.ttl modules/*.ttl imports/fragments/*.ttl scripts/metadata.ttl
```
