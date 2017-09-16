import requests


def get_city(latitude, longitude):
    api_key = "AIzaSyCENhThoSzi_OSy7mNRGGcd4U5U9xGaWHM"
    query = "%s,%s" % (latitude, longitude)
    response = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json?key=%s&result_type=locality&language=de&latlng=%s" % (
        api_key, query))

    results = response.json()

    if len(results) == 0:
        return None

    city = results["results"][0]["address_components"][0]["long_name"]
    return city
