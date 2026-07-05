import json

from backend.transitland.extractors.stops_extractor import StopsExtractor


extractor = StopsExtractor()

stops = extractor.extract()

with open(
    "data/raw/berlin_stops_raw.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        stops,
        f,
        indent=4,
        ensure_ascii=False
    )

print(
    f"Saved {len(stops)} stops"
)