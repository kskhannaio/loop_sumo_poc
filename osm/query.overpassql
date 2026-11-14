[out:xml][timeout:120];
// roads for the Madiwala loop plus a margin, for SUMO's netconvert
(
  way["highway"~"^(trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|residential|unclassified|living_street)$"](12.9215,77.6115,12.9330,77.6245);
);
(._;>;);
out body;
