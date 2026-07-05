from backend.transitland.clients.transit_client import TransitLandClient

client = TransitLandClient()

data = client.search_operators("Berlin")

print("keys:", data.keys())

operators = data.get("operators", [])

for op in operators:

    print("name:", op.get("name"))
    print("onestop_id:", op.get("onestop_id"))
    print("-"*30)