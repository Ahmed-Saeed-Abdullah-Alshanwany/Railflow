from backend.transitland.clients.transit_client import TransitLandClient

client = TransitLandClient()

data = client.get_routes_by_operator(
    "o-u33-s~bahnberlingmbh"
)

print(data.keys())

print(data.get("meta"))

routes = data.get("routes", [])

print("Number:", len(routes))

for route in routes[:10]:

    print(
        "short:",
        route.get("route_short_name")
    )

    print(
        "long:",
        route.get("route_long_name")
    )

    print(
        "id:",
        route.get("onestop_id")
    )

    print("=" * 30)