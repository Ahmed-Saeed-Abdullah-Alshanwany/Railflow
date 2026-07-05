from backend.transitland.clients.transit_client import TransitLandClient


class StopsExtractor:

    def __init__(self):

        self.client = TransitLandClient()


    def extract(self, operator_onestop_id: str = "o-u33-s~bahnberlingmbh", limit: int = 100, after: int = None):
        data = self.client.get_stops(
            served_by_onestop_ids=operator_onestop_id,
            limit=limit,
            after=after
        )
        stops = data.get("stops", [])
        meta = data.get("meta", {})
        next_cursor = meta.get("after")
        return stops, next_cursor