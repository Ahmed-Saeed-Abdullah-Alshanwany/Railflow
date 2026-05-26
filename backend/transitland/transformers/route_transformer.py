class RouteTransformer:

    def transform(self, routes):

        cleaned = []

        for route in routes:

            stops = []

            route_stops = route.get(
                "route_stops",
                []
            )

            for rs in route_stops:

                stop = rs.get(
                    "stop",
                    {}
                )

                stop_name = stop.get(
                    "stop_name",
                    ""
                )

                # تصنيف نوع المحطة
                transport_type = "other"

                if stop_name.startswith("S+U"):
                    transport_type = "interchange"

                elif stop_name.startswith("S "):
                    transport_type = "suburban_rail"

                elif stop_name.startswith("U "):
                    transport_type = "metro"

                stops.append({

                    "stop_id":
                    stop.get(
                        "stop_id"
                    ),

                    "stop_name":
                    stop_name,

                    "transport_type":
                    transport_type
                })

            cleaned.append({

                "route_id":
                route.get(
                    "onestop_id"
                ),

                "line":
                route.get(
                    "route_short_name"
                ),

                "agency":
                route.get(
                    "agency",
                    {}
                ).get(
                    "agency_name"
                ),

                "stops":
                stops
            })

        return cleaned