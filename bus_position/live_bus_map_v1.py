from flask import Flask, render_template_string, request
import folium
from google.transit import gtfs_realtime_pb2
from google.protobuf.json_format import MessageToDict
from requests import get
from datetime import datetime, timedelta
import pandas as pd

# Flask app setup
app = Flask(__name__)

# List of categories to fetch
categories = [
    {"name": "rapid-bus-kl", "url": "https://api.data.gov.my/gtfs-realtime/vehicle-position/prasarana?category=rapid-bus-kl"},
    {"name": "rapid-bus-mrtfeeder", "url": "https://api.data.gov.my/gtfs-realtime/vehicle-position/prasarana?category=rapid-bus-mrtfeeder"},
    {"name": "rapid-bus-kuantan", "url": "https://api.data.gov.my/gtfs-realtime/vehicle-position/prasarana?category=rapid-bus-kuantan"},
    {"name": "rapid-bus-penang", "url": "https://api.data.gov.my/gtfs-realtime/vehicle-position/prasarana?category=rapid-bus-penang"},
    {"name": "mybas-johor", "url": "https://api.data.gov.my/gtfs-realtime/vehicle-position/mybas-johor"}
]

# Function to fetch and process bus data
def fetch_bus_data(url):
    feed = gtfs_realtime_pb2.FeedMessage()
    response = get(url)
    feed.ParseFromString(response.content)
    vehicle_positions = [MessageToDict(entity.vehicle) for entity in feed.entity]
    return pd.json_normalize(vehicle_positions)

# Function to convert UTC to UTC+8
def convert_to_utc8(utc_timestamp):
    if utc_timestamp == 'N/A':
        return 'N/A'
    utc_time = datetime.utcfromtimestamp(int(utc_timestamp))
    utc8_time = utc_time + timedelta(hours=8)
    return utc8_time.strftime('%Y-%m-%d %H:%M:%S UTC+8')

# Function to generate the map
def create_map(category=None, route=None):
    m = folium.Map(location=[3.1390, 101.6869], zoom_start=7)
    bounds = []
    routes_available = set()

    for cat in categories:
        if category and cat["name"] != category:
            continue  # Skip if not the selected category

        df = fetch_bus_data(cat["url"])
        if not df.empty:
            for _, row in df.iterrows():
                latitude = row.get('position.latitude')
                longitude = row.get('position.longitude')
                speed = row.get('position.speed')  # May be None
                bearing = row.get('position.bearing')
                route_id = row.get('trip.routeId', 'Unknown')  # Route information
                gps_time = row.get('timestamp', 'N/A')

                # Convert GPS time to UTC+8
                gps_time_utc8 = convert_to_utc8(gps_time)

                if latitude is not None and longitude is not None:
                    routes_available.add(route_id)
                    if route and route != route_id:
                        continue  # Skip if not the selected route

                    color = (
                        "blue" if speed is None else
                        "red" if speed == 0 else
                        "orange" if speed < 10 else
                        "yellow" if speed < 30 else
                        "green"
                    )
                    bounds.append((latitude, longitude))

                    folium.Marker(
                        location=(latitude, longitude),
                        icon=folium.DivIcon(
                            html=f"""
                            <div style="
                                width: 10px; 
                                height: 10px; 
                                background-color: {color}; 
                                border-radius: 50%; 
                                border: 1px solid black;">
                            </div>
                            """
                        ),
                        tooltip=f"Category: {cat['name']}<br>"
                                f"Route ID: {route_id}<br>"
                                f"Bus ID: {row.get('vehicle.id', 'N/A')}<br>"
                                f"Speed: {speed if speed is not None else 'N/A'} km/h<br>"
                                f"Bearing: {bearing if bearing is not None else 'N/A'}<br>"
                                f"GPS Time: {gps_time_utc8}"
                    ).add_to(m)

    if bounds:
        m.fit_bounds(bounds)

    # Add a legend in the upper-right corner
    legend_html = """
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 150px; height: 140px; 
                background-color: white; z-index:9999; font-size:14px; 
                border:2px solid grey; padding: 10px;">
        <b>Legend</b><br>
        <i style="background:red; width:10px; height:10px; display:inline-block;"></i> Stopped<br>
        <i style="background:orange; width:10px; height:10px; display:inline-block;"></i> Slow<br>
        <i style="background:yellow; width:10px; height:10px; display:inline-block;"></i> Moderate<br>
        <i style="background:green; width:10px; height:10px; display:inline-block;"></i> Fast<br>
        <i style="background:blue; width:10px; height:10px; display:inline-block;"></i> No Speed Data
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    return m, sorted(routes_available)

# Serve the map in Flask
@app.route('/', methods=['GET', 'POST'])
def index():
    category = request.form.get('category', None)
    route = request.form.get('route', None)

    latest_map, routes_available = create_map(category, route)
    map_html = latest_map._repr_html_()

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bus Positions</title>
        <style>
            #map {
                height: 90vh; /* Adjust map to fit the screen */
            }
        </style>
    </head>
    <body>
        <h1>Live Bus Positions</h1>
        <form method="POST">
            <label for="category">Select Category:</label>
            <select name="category" id="category" onchange="this.form.submit()">
                <option value="">All</option>
                {% for cat in categories %}
                    <option value="{{ cat.name }}" {% if cat.name == category %}selected{% endif %}>
                        {{ cat.name }}
                    </option>
                {% endfor %}
            </select>
            
            <label for="route">Select Route:</label>
            <select name="route" id="route" {% if not category %}disabled{% endif %} onchange="this.form.submit()">
                <option value="">All</option>
                {% for r in routes %}
                    <option value="{{ r }}" {% if r == route %}selected{% endif %}>
                        {{ r }}
                    </option>
                {% endfor %}
            </select>
        </form>

        <button onclick="getCurrentLocation()">Show Current Location</button>
        <button onclick="location.reload()">Refresh Map</button>

        <div id="map">{{ map_html|safe }}</div>

        <script>
            function getCurrentLocation() {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(function(position) {
                        alert("Current Location:\nLatitude: " + position.coords.latitude +
                              "\nLongitude: " + position.coords.longitude);
                    });
                } else {
                    alert("Geolocation is not supported by this browser.");
                }
            }
        </script>
    </body>
    </html>
    """, map_html=map_html, categories=categories, category=category, routes=routes_available, route=route)

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
