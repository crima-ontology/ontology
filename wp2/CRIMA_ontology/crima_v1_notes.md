[•] crima_v1.ttl :

--- isAbout ••• http://www.semanticweb.org/CRIMA#isAbout [frbr:P129:isAbout] ???
--- notDisjoint ••• http://www.semanticweb.org/CRIMA#notDisjoint ???

--- hasResult ••• http://www.semanticweb.org/CRIMA#hasResult --> http://www.w3.org/ns/sosa/hasResult
--- [dcterms:subject] http://purl.org/dc/terms/subject [introduced as ObjectProperty!] ::: [inverse of] ??? [+]
--- dcat:Resource [+]
--- dcat:Dataset [+]
--- :Drought [+]
--- [Connection --from--> ICFactor] --> [ICconnection --from--> ICFactor] [typo]
--- inverse of "sosa:isFeatureOfInterestOf": http://www.w3.org/ns/sosa/hasFeatureOfInterest ::: sosa:hasFeatureOfInterest rdf:type owl:ObjectProperty [+]
--- sub-class of "sosa:hasFeatureOfInterest": http://knowwheregraph/ontology/deo#hasHazardOfInterest ::: deo:hasHazardOfInterest [+]
--- sub-class of "sosa:hasFeatureOfInterest": http://knowwheregraph/ontology/deo#hasImpactOfInterest ::: deo:hasImpactOfInterest [+]
--- sub-class of "sosaObservation": :IntensityObservation [+]
--- sub-class of "sosaObservation": :SeverityObservation [+]
--- sub-class of "deo:HazardProperty": :DroughtObservableProperty [+]
--- sub-class of "crima:DroughtObservableProperty": several classes added (to be completed) [+]
--- constantParticipantOf ••• https://w3id.org/DOLCE/OWL/DOLCEbasic#constantParticipantOf [+]
--- sub-class of "db:constantParticipantOf": :participates [+]
--- time (crima:hasTime removed) ••• {time:TemporalEntity; time:TimeInterval; time:Instant; time:hasBeginning; time:hasEnd; time:hasTime = crima:hasTemporalExtent} [+]
--- space ••• {geo:hasGeometry; geo:Feature; geo:Geometry; geo:SpatialObject; crima:hasSpatialExtent} [+]
