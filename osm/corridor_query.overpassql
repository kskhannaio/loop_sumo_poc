[out:xml][timeout:180];
// roads along the elevated-corridor contract drawings: Madiwala loop south to Bommanahalli, west towards Koramangala.
// Used to georeference the contract drawings (qgis/contract/extract.py).
(
  way["highway"~"^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|residential|unclassified|living_street|service)$"](12.900,77.600,12.937,77.640);
);
(._;>;);
out body;
