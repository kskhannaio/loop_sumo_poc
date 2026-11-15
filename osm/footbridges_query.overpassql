[out:xml][timeout:60];
// foot over bridges and their stairs around the Madiwala loop (same box as query.overpassql).
// build_net.py joins them to the nearest carriageway so people in the model can use them.
(
  way["highway"~"^(footway|steps)$"]["bridge"](12.9215,77.6115,12.9330,77.6245);
  way["highway"="steps"](12.9215,77.6115,12.9330,77.6245);
);
(._;>;);
out body;
