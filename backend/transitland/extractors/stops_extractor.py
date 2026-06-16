from backend.transitland.clients.transit_client import TransitLandClient


class StopsExtractor:

    def __init__(self):

        self.client = TransitLandClient()


    def extract(self):

        operator = (
            "o-u33-s~bahnberlingmbh"
        )

        data = self.client.get_stops(
            operator,
            limit=100
        )

        return data