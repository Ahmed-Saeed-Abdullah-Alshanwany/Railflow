from backend.transitland.extractors.berlin_extractor import (
    BerlinExtractor
)

extractor = BerlinExtractor()

routes = extractor.extract_routes()

print(
    f"\nFinal routes count: {len(routes)}"
)