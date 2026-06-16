import json

from backend.transitland.transformers.route_transformer import RouteTransformer


with open(
    "data/raw/berlin_routes.json",
    encoding="utf-8"
) as f:

    routes = json.load(f)


transformer = RouteTransformer()

cleaned = transformer.transform(
    routes
)

with open(
    "data/processed/berlin_routes_clean.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        cleaned,
        f,
        indent=4,
        ensure_ascii=False
    )


print(
    f"Saved {len(cleaned)} routes"
)