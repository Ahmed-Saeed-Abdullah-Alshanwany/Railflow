from backend.transitland.clients.transit_client import (
    TransitLandClient
)


class BerlinExtractor:

    def __init__(self):

        self.client = TransitLandClient()

        self.operator_id = (
            "o-u33-s~bahnberlingmbh"
        )

    def extract_routes(self):

        all_routes = []

        after = None

        while True:

            data = self.client.get_routes_by_operator(
                self.operator_id,
                limit=50,
                after=after
            )

            routes = data.get("routes", [])

            all_routes.extend(routes)

            meta = data.get("meta", {})

            after = meta.get("after")

            print(
                f"Collected routes: {len(all_routes)}"
            )

            if not after:
                break

        return all_routes