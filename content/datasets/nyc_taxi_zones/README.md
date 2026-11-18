# nyc_taxi_zones

The 263 shapes of New York City's taxi zones (260 distinct LocationIDs – zones 56 and 103 consist of
several shapes), in GPS coordinates (WGS 84, longitude/latitude). Used by the EXA-GS-100 dashboard map and
the geospatial lesson of EXA-DEV-100.

| File | Contents |
|---|---|
| `taxi_zones.geojson` | 263 features, properties `LocationID`, `zone`, `borough`; coordinates rounded to 5 decimals (about 1 m) |
| `taxi_zones.csv` | 260 rows: `LOCATION_ID`, `BOROUGH`, `ZONE`, `SHAPE_WKT` (MULTIPOLYGON, split shapes merged) |

**Source:** NYC Open Data, dataset *NYC Taxi Zones* (`8meu-9t5y`),
<https://data.cityofnewyork.us/api/v3/views/8meu-9t5y/query.geojson?accessType=DOWNLOAD>, downloaded
2026-11-18. The zone names match the NYC TLC lookup file
<https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv>.
