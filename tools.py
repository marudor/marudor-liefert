from datetime import datetime
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



def parse_date(text):
    today = datetime.now()

    segments = text.strip(".").split(".", 2)
    valid_date = True
    try:
        day = int(segments[0])
    except IndexError:
        day = today.day
    except ValueError:
        valid_date = False

    try:
        month = int(segments[1])
    except IndexError:
        month = today.month if day >= today.day else today.month + 1
    except ValueError:
        valid_date = False

    try:
        year = int(segments[2])
        if year < 100:
            year += 2000
    except IndexError:
        year = today.year
    except ValueError:
        valid_date = False

    if valid_date:
        return datetime(year, month, day)
    else:
        return None