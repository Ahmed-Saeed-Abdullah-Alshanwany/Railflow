from backend.transitland.clients.transit_client import TransitLandClient

client = TransitLandClient()

for keyword in ["BVG", "VBB", "Berlin"]:

    print(f"\n========== {keyword} ==========")

    data = client.get_feeds(
        limit=10,
        search=keyword
    )

    for feed in data["feeds"]:

        print(
            "name:",
            feed.get("name")
        )

        print(
            "onestop_id:",
            feed.get("onestop_id")
        )

        print("-"*30)