import requests
import time

def get_country_coordinates(country_names):
    base_url = "https://nominatim.openstreetmap.org/search"
    results = []
    headers = {"User-Agent": "FlightDataProject/1.0"}

    for name in country_names:
        params = {
            "q": name,
            "format": "json",
            "limit": 1,
            "countrycodes": ""  # можно уточнить, но для стран часто не нужно
        }
        resp = requests.get(base_url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        if data:
            results.append({
                "name": name,
                "latitude": float(data[0]["lat"]),
                "longitude": float(data[0]["lon"])
            })
        else:
            print(f"Не удалось найти координаты для {name}")

        time.sleep(1)  # чтобы не превысить лимиты Nominatim

    return results

def get_airplanes_in_area(lat, lon, radius_km=500):
    """
    lat, lon — центр области (из Nominatim)
    radius_km — радиус в км (приближённо)
    Возвращает список самолётов в JSON-формате от OpenSky
    """
    # Переводим км в градусы (грубо: 1 градус ~ 111 км)
    radius_deg = radius_km / 111.0

    min_lat = lat - radius_deg
    max_lat = lat + radius_deg
    min_lon = lon - radius_deg
    max_lon = lon + radius_deg

    url = "https://opensky-network.org/api/states/all"
    params = {
        "lamin": min_lat,
        "lamax": max_lat,
        "lomin": min_lon,
        "lomax": max_lon
    }

    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()


    return data.get("states", [])