from backend.transitland.clients.transit_client import TransitLandClient

client = TransitLandClient()

data = client.get_feeds()

print(data.keys())