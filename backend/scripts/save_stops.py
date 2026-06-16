import json

from backend.transitland.extractors.stops_extractor import (
    StopsExtractor
)

extractor=StopsExtractor()

stops=extractor.extract()

clean=[]

for stop in stops:

    coords=(
        stop.get("geometry",{})
        .get("coordinates",[None,None])
    )

    clean.append({

        "stop_id":
        stop.get("stop_id"),

        "stop_name":
        stop.get("stop_name"),

        "onestop_id":
        stop.get("onestop_id"),

        "lat":
        coords[1],

        "lon":
        coords[0],

        "platform":
        stop.get(
            "platform_code"
        ),

        "wheelchair":
        stop.get(
            "wheelchair_boarding"
        ),

        "location_type":
        stop.get(
            "location_type"
        ),

        "country":
        stop.get(
            "place",{}
        ).get(
            "adm0_name"
        ),

        "state":
        stop.get(
            "place",{}
        ).get(
            "adm1_name"
        )
    })

with open(
    "data/raw/berlin_stops.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        clean,
        f,
        ensure_ascii=False,
        indent=4
    )

print(
    "Saved",
    len(clean),
    "stops"
)