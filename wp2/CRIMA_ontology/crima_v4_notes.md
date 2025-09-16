[•] crima_v4.ttl
--- Platform : http://www.w3.org/ns/sosa/Platform [+]
--- hosts : http://www.w3.org/ns/sosa/hosts [+]
--- isHostedBy :  http://www.w3.org/ns/sosa/isHostedBy [+]
--- System : http://www.w3.org/ns/sosa/System [+]
--- Few properties/indices for Drought have been added, as an example (see also 2025.09.15 email to eurac). 

--- Impact Chain connections (see "Guidelines"): 
• [Affect]: impch:source some impch:Vulnerability; impch:target some impch:Impact 
• [LeadsTo]: impch:source some (impch:HazardFactor or impch:ImpactFactor); impch:target some (impch:HazardFactor or impch:ImpactFactor)
• [ImpactsOn]: impch:source some impch:ImpactFactor; impch:target some impch:ExposureFactor
• [Mitigates]: impch:source some impch:AdaptationFactor; impch:target some (impch:VulnerabilityFactor or impch:ImpactFactor or impch:RiskFactor)

--- Impact Chain factors renaming ('IC' removed)
--- [impch:] prefix dedicated to the entities of the Impact Chain module
--- full dolce_basic_owl imported