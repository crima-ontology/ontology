--- db:Particular --subClassOf--> sosa:FeatureOfInterest
--- sosa-common entities consistently applied (instead of a mixture of sosa and ssn)
--- sosa:Observation --rdfs:subClassOf--> db:Event
--- sosa:Propery --rdfs:subClassOf--> db:Quality

--- [added]
###  http://dbpedia.org/ontology/ArchitecturalStructure [and subclasses]
###  http://dbpedia.org/ontology/Place [and subclasses, minus 'CelestialBody' and subclasses]

--- [added]
###  http://www.opengis.net/ont/geosparql#sfContains
###  http://www.opengis.net/ont/geosparql#sfCrosses
###  http://www.opengis.net/ont/geosparql#sfDisjoint
###  http://www.opengis.net/ont/geosparql#sfEquals
###  http://www.opengis.net/ont/geosparql#sfIntersects
###  http://www.opengis.net/ont/geosparql#sfOverlaps
###  http://www.opengis.net/ont/geosparql#sfTouches
###  http://www.opengis.net/ont/geosparql#sfWithin
###  http://www.opengis.net/ont/geosparql#hasSize

--- {dbo:ArchitecturalStructure, dbo:Place} --subClassOf--> geo:Feature

--- [???] geo:sfOverlaps --subClassOf--> db:constantlyOverlaps 
--- [???] hip:SpecificHazard --subClassOf--> impch:HazardFactor
--- [???] geo:SpatialObject  --subClassOf--> :Exposure
