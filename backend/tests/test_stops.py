from backend.transitland.extractors.stops_extractor import StopsExtractor


extractor = StopsExtractor()

stops = extractor.extract()

print(
    "count:",
    len(stops)
)

for stop in stops[:5]:

    print(
        stop.get(
            "stop_name"
        )
    )

    print(
        stop.get(
            "stop_id"
        )
    )

    print("-"*30)