from flask import Flask, jsonify
from google.transit import gtfs_realtime_pb2
from google.protobuf.json_format import MessageToDict
from flask_cors import CORS
from requests import get

app = Flask(__name__)
CORS(app)

URLS = {
    "rapid-bus-kl": "https://api.data.gov.my/gtfs-realtime/vehicle-position/prasarana?category=rapid-bus-kl",
    "rapid-bus-mrtfeeder": "https://api.data.gov.my/gtfs-realtime/vehicle-position/prasarana?category=rapid-bus-mrtfeeder",
    "rapid-bus-penang": "https://api.data.gov.my/gtfs-realtime/vehicle-position/prasarana?category=rapid-bus-penang",
    "rapid-bus-kuantan": "https://api.data.gov.my/gtfs-realtime/vehicle-position/prasarana?category=rapid-bus-kuantan",
    "mybas-johor": "https://api.data.gov.my/gtfs-realtime/vehicle-position/mybas-johor",
}

@app.route('/vehicles', methods=['GET'])
def get_vehicles():
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }

    for category, url in URLS.items():
        feed = gtfs_realtime_pb2.FeedMessage()
        response = get(url)
        feed.ParseFromString(response.content)

        for entity in feed.entity:
            vehicle = MessageToDict(entity).get('vehicle', {})
            position = vehicle.get('position', {})
            route_id = vehicle.get('trip', {}).get('routeId')  # Extract routeId here

            if 'latitude' in position and 'longitude' in position:
                geojson["features"].append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [position["longitude"], position["latitude"]]
                    },
                    "properties": {
                        "id": vehicle.get("vehicle", {}).get("id"),
                        "category": category,
                        "speed": position.get("speed"),
                        "bearing": position.get("bearing"),
                        "routeId": route_id  # Include routeId
                    }
                })

    return jsonify(geojson)

if __name__ == '__main__':
    app.run(debug=True)
