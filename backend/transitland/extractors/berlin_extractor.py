from backend.transitland.clients.transit_client import TransitLandClient


class BerlinExtractor:

    OPERATOR_ID = "o-u33-s~bahnberlingmbh"

    def __init__(self):
        self.client = TransitLandClient()

    def extract_routes(self, limit: int = 50, after: int = None):
        data = self.client.get_routes_by_operator(
            operator_onestop_id=self.OPERATOR_ID,
            limit=limit,
            after=after
        )
        routes = data.get("routes", [])
        meta = data.get("meta", {})
        next_cursor = meta.get("after")
        return routes, next_cursor