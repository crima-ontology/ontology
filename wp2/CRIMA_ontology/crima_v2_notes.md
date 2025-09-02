[•] crima_v2.ttl:

--- geo:hasSerialization [owl:DatatypeProperty] : http://www.opengis.net/ont/geosparql#hasSerialization [+]
--- geo:asWKT [owl:DatatypeProperty[ : http://www.opengis.net/ont/geosparql#asWKT [+]
--- [datatype] geo:wktLiteral : http://www.opengis.net/ont/geosparql#wktLiteral [+]
--- http://www.semanticweb.org/CRIMA#from --> http://www.semanticweb.org/CRIMA#source [renaming]
--- http://www.semanticweb.org/CRIMA#to --> http://www.semanticweb.org/CRIMA#target [renaming]

--- as: [prefix] : https://www.w3.org/ns/activitystreams# [+]
--- as:latitude : https://www.w3.org/ns/activitystreams#latitude [+]
--- as:longitude : https://www.w3.org/ns/activitystreams#longitude [+]

--- qudt: [prefix] : http://qudt.org/schema/qudt
--- qudt:numericValue [owl:DatatypeProperty] : http://qudt.org/schema/qudt/numericValue
--- qudt:Unit : http://qudt.org/schema/qudt/Unit
--- qudt:hasUnit : http://qudt.org/schema/qudt/hasUnit

--- dtype:[prefix] : http://www.linkedmodel.org/schema/dtype# [+]
--- [datatype] dtype:numericUnion : http://www.linkedmodel.org/schema/dtype#numericUnion [+]

--- as: [prefix] : https://www.w3.org/ns/activitystreams#
--- as:Place : https://www.w3.org/ns/activitystreams#Place
