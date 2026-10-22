"""Towns on the US interstate network, used as via points for alternative routes.

A via point placed at an arbitrary offset often snaps onto a farm track; a
town on an interstate produces a route a dispatcher would actually consider.
Coordinates are approximate city centres.
"""

US_VIA_CITIES: tuple[tuple[str, float, float], ...] = (
    # West
    ("Seattle, WA", 47.61, -122.33), ("Spokane, WA", 47.66, -117.43), ("Yakima, WA", 46.60, -120.51),
    ("Portland, OR", 45.52, -122.68), ("Pendleton, OR", 45.67, -118.79), ("Bend, OR", 44.06, -121.31),
    ("Eugene, OR", 44.05, -123.09), ("Medford, OR", 42.33, -122.87), ("Redding, CA", 40.59, -122.39),
    ("Sacramento, CA", 38.58, -121.49), ("San Francisco, CA", 37.77, -122.42), ("Fresno, CA", 36.74, -119.79),
    ("Bakersfield, CA", 35.37, -119.02), ("Barstow, CA", 34.90, -117.02), ("Los Angeles, CA", 34.05, -118.24),
    ("San Diego, CA", 32.72, -117.16), ("El Centro, CA", 32.79, -115.56), ("Needles, CA", 34.85, -114.61),
    ("Blythe, CA", 33.61, -114.60), ("Reno, NV", 39.53, -119.81), ("Winnemucca, NV", 40.97, -117.74),
    ("Elko, NV", 40.83, -115.76), ("Wells, NV", 41.11, -114.96), ("Ely, NV", 39.25, -114.89),
    ("Las Vegas, NV", 36.17, -115.14), ("Boise, ID", 43.62, -116.20), ("Twin Falls, ID", 42.56, -114.46),
    ("Pocatello, ID", 42.87, -112.45), ("Idaho Falls, ID", 43.49, -112.03), ("Missoula, MT", 46.87, -113.99),
    ("Butte, MT", 46.00, -112.53), ("Bozeman, MT", 45.68, -111.04), ("Billings, MT", 45.78, -108.50),
    ("Great Falls, MT", 47.50, -111.30), ("Salt Lake City, UT", 40.76, -111.89), ("Ogden, UT", 41.22, -111.97),
    ("Provo, UT", 40.23, -111.66), ("St. George, UT", 37.10, -113.58), ("Green River, UT", 38.99, -110.16),
    ("Rock Springs, WY", 41.59, -109.20), ("Rawlins, WY", 41.79, -107.24), ("Laramie, WY", 41.31, -105.59),
    ("Cheyenne, WY", 41.14, -104.82), ("Casper, WY", 42.87, -106.31), ("Sheridan, WY", 44.80, -106.96),
    ("Grand Junction, CO", 39.06, -108.55), ("Denver, CO", 39.74, -104.99), ("Colorado Springs, CO", 38.83, -104.82),
    ("Pueblo, CO", 38.25, -104.61), ("Kingman, AZ", 35.19, -114.05), ("Flagstaff, AZ", 35.20, -111.65),
    ("Phoenix, AZ", 33.45, -112.07), ("Tucson, AZ", 32.22, -110.97), ("Yuma, AZ", 32.69, -114.63),
    ("Gallup, NM", 35.53, -108.74), ("Albuquerque, NM", 35.08, -106.65), ("Santa Fe, NM", 35.69, -105.94),
    ("Las Cruces, NM", 32.32, -106.76), ("Tucumcari, NM", 35.17, -103.72),
    # Plains & Texas
    ("El Paso, TX", 31.76, -106.49), ("Midland, TX", 32.00, -102.08), ("Lubbock, TX", 33.58, -101.86),
    ("Amarillo, TX", 35.22, -101.83), ("Abilene, TX", 32.45, -99.73), ("San Angelo, TX", 31.46, -100.44),
    ("Fort Worth, TX", 32.76, -97.33), ("Dallas, TX", 32.78, -96.80), ("Waco, TX", 31.55, -97.15),
    ("Austin, TX", 30.27, -97.74), ("San Antonio, TX", 29.42, -98.49), ("Houston, TX", 29.76, -95.37),
    ("Beaumont, TX", 30.08, -94.13), ("Tyler, TX", 32.35, -95.30), ("Texarkana, TX", 33.43, -94.05),
    ("Laredo, TX", 27.51, -99.51), ("Corpus Christi, TX", 27.80, -97.40), ("Wichita Falls, TX", 33.91, -98.49),
    ("Oklahoma City, OK", 35.47, -97.52), ("Tulsa, OK", 36.15, -95.99), ("Wichita, KS", 37.69, -97.34),
    ("Salina, KS", 38.84, -97.61), ("Hays, KS", 38.88, -99.33), ("Topeka, KS", 39.05, -95.68),
    ("Kansas City, MO", 39.10, -94.58), ("North Platte, NE", 41.12, -100.77), ("Grand Island, NE", 40.93, -98.34),
    ("Lincoln, NE", 40.81, -96.70), ("Omaha, NE", 41.26, -95.93), ("Sioux Falls, SD", 43.54, -96.73),
    ("Rapid City, SD", 44.08, -103.23), ("Fargo, ND", 46.88, -96.79), ("Bismarck, ND", 46.81, -100.78),
    # Midwest
    ("Minneapolis, MN", 44.98, -93.27), ("Duluth, MN", 46.79, -92.10), ("Rochester, MN", 44.02, -92.47),
    ("Des Moines, IA", 41.59, -93.62), ("Cedar Rapids, IA", 41.98, -91.67), ("Davenport, IA", 41.52, -90.58),
    ("Sioux City, IA", 42.50, -96.40), ("Madison, WI", 43.07, -89.40), ("Milwaukee, WI", 43.04, -87.91),
    ("Green Bay, WI", 44.51, -88.01), ("Eau Claire, WI", 44.81, -91.50), ("Chicago, IL", 41.88, -87.63),
    ("Rockford, IL", 42.27, -89.09), ("Peoria, IL", 40.69, -89.59), ("Springfield, IL", 39.78, -89.65),
    ("Champaign, IL", 40.12, -88.24), ("St. Louis, MO", 38.63, -90.20), ("Columbia, MO", 38.95, -92.33),
    ("Springfield, MO", 37.21, -93.29), ("Joplin, MO", 37.08, -94.51), ("Indianapolis, IN", 39.77, -86.16),
    ("Fort Wayne, IN", 41.08, -85.14), ("Evansville, IN", 37.97, -87.57), ("Detroit, MI", 42.33, -83.05),
    ("Grand Rapids, MI", 42.96, -85.67), ("Lansing, MI", 42.73, -84.56), ("Toledo, OH", 41.65, -83.54),
    ("Columbus, OH", 39.96, -83.00), ("Cincinnati, OH", 39.10, -84.51), ("Cleveland, OH", 41.50, -81.69),
    ("Louisville, KY", 38.25, -85.76), ("Lexington, KY", 38.04, -84.50),
    # South
    ("Little Rock, AR", 34.75, -92.29), ("Fort Smith, AR", 35.39, -94.40), ("Memphis, TN", 35.15, -90.05),
    ("Nashville, TN", 36.16, -86.78), ("Knoxville, TN", 35.96, -83.92), ("Chattanooga, TN", 35.05, -85.31),
    ("Shreveport, LA", 32.53, -93.75), ("Baton Rouge, LA", 30.45, -91.19), ("New Orleans, LA", 29.95, -90.07),
    ("Lake Charles, LA", 30.23, -93.22), ("Jackson, MS", 32.30, -90.18), ("Meridian, MS", 32.36, -88.70),
    ("Birmingham, AL", 33.52, -86.80), ("Montgomery, AL", 32.37, -86.30), ("Mobile, AL", 30.69, -88.04),
    ("Atlanta, GA", 33.75, -84.39), ("Macon, GA", 32.84, -83.63), ("Savannah, GA", 32.08, -81.09),
    ("Tallahassee, FL", 30.44, -84.28), ("Jacksonville, FL", 30.33, -81.66), ("Orlando, FL", 28.54, -81.38),
    ("Tampa, FL", 27.95, -82.46), ("Miami, FL", 25.76, -80.19),
    # East
    ("Columbia, SC", 34.00, -81.03), ("Charlotte, NC", 35.23, -80.84), ("Greensboro, NC", 36.07, -79.79),
    ("Raleigh, NC", 35.78, -78.64), ("Asheville, NC", 35.60, -82.55), ("Roanoke, VA", 37.27, -79.94),
    ("Richmond, VA", 37.54, -77.44), ("Charleston, WV", 38.35, -81.63), ("Washington, DC", 38.91, -77.04),
    ("Baltimore, MD", 39.29, -76.61), ("Harrisburg, PA", 40.27, -76.88), ("Pittsburgh, PA", 40.44, -80.00),
    ("Philadelphia, PA", 39.95, -75.17), ("Scranton, PA", 41.41, -75.66), ("New York, NY", 40.71, -74.01),
    ("Albany, NY", 42.65, -73.76), ("Syracuse, NY", 43.05, -76.15), ("Buffalo, NY", 42.89, -78.88),
    ("Hartford, CT", 41.76, -72.68), ("Boston, MA", 42.36, -71.06), ("Portland, ME", 43.66, -70.26),
)
