import requests
import os
from dotenv import load_dotenv
from models import AgencyModel, StopModel, RouteModel

def test_fetch_100():
    load_dotenv()
    api_key = os.getenv("TRANSITLAND_API_KEY")
    headers = {"apikey": api_key}
    
    operator_id = "o-u33-s~bahnberlingmbh"
    limit = 100
    
    endpoints = {
        "agencies": (f"https://transit.land/api/v2/rest/agencies?operator_onestop_id={operator_id}&limit={limit}", AgencyModel),
        "stops": (f"https://transit.land/api/v2/rest/stops?served_by_onestop_ids={operator_id}&limit={limit}", StopModel),
        "routes": (f"https://transit.land/api/v2/rest/routes?operator_onestop_id={operator_id}&limit={limit}", RouteModel)
    }
    
    print("=== Testing Fetch and Validation (Limit 100) ===")
    
    for entity, (url, model_class) in endpoints.items():
        print(f"\nFetching {entity}...")
        try:
            res = requests.get(url, headers=headers)
            res.raise_for_status()
            data = res.json()
            items = data.get(entity, [])
            
            print(f"-> Fetched {len(items)} items from API.")
            
            valid_items = []
            for item in items:
                try:
                    valid_item = model_class(**item)
                    valid_items.append(valid_item)
                except Exception as e:
                    print(f"Validation Error in {entity} for ID {item.get('id')}: {e}")
            
            print(f"-> Successfully validated {len(valid_items)} {entity} using Pydantic Schema.")
            
            if valid_items:
                print("-> Example of first validated item:")
                print(valid_items[0].model_dump_json(indent=2))
                
        except Exception as e:
            print(f"Error fetching {entity}: {e}")

if __name__ == "__main__":
    test_fetch_100()
