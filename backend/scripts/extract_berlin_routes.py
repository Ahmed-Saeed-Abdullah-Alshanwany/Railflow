import json
from pathlib import Path

from backend.transitland.extractors.berlin_extractor import BerlinExtractor


extractor = BerlinExtractor()

routes = extractor.extract_routes()

output = Path(
    "data/raw/berlin_routes.json"
)

with open(
    output,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        routes,
        f,
        indent=4,
        ensure_ascii=False
    )

print(
    f"Saved {len(routes)} routes"
)

print(
    f"File: {output}"
)