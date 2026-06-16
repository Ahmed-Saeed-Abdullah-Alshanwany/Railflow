import os
import requests
from dotenv import load_dotenv

load_dotenv()


class TransitLandClient:

    BASE_URL = "https://transit.land/api/v2/rest"

    def __init__(self):

        self.api_key = os.getenv(
            "TRANSITLAND_API_KEY"
        )

        if not self.api_key:
            raise ValueError(
                "TRANSITLAND_API_KEY not found"
            )

        self.headers = {
            "apikey": self.api_key
        }

    def get_routes_by_operator(
        self,
        operator_onestop_id,
        limit=20,
        after=None
    ):

        url = f"{self.BASE_URL}/routes"

        params = {
            "operator_onestop_id":
            operator_onestop_id,

            "limit":
            limit,

            "include_stops":
            "true"
        }

        if after:
            params["after"] = after

        response = requests.get(
            url,
            headers=self.headers,
            params=params
        )

        response.raise_for_status()

        return response.json()

    def get_stops(
        self,
        served_by_onestop_ids,
        limit=100
    ):

        url = f"{self.BASE_URL}/stops"

        response = requests.get(
            url,
            headers=self.headers,
            params={
                "served_by_onestop_ids":
                served_by_onestop_ids,

                "limit":
                limit
            }
        )

        response.raise_for_status()

        return response.json()