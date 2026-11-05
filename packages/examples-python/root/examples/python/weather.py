import sys
import kt
import requests

DAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
SKY = [(0, "ясно"), (3, "облачно"), (48, "туман"), (57, "морось"), (67, "дождь"), (77, "снег"),
       (82, "ливень"), (86, "снегопад"), (99, "гроза")]


def sky(code):
    for top, word in SKY:
        if code <= top:
            return word
    return ""


def color(t):
    steps = [(-15, 69), (-5, 75), (0, 117), (8, 152), (15, 186), (22, 221), (28, 209), (99, 203)]
    for top, c in steps:
        if t <= top:
            return c
    return 203


def weekday(day):
    y, m, d = [int(x) for x in day.split("-")]
    if m < 3:
        y -= 1
    w = (y + y // 4 - y // 100 + y // 400 + [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4][m - 1] + d) % 7
    return DAYS[(w + 6) % 7]


if len(sys.argv) > 1:
    city = " ".join(sys.argv[1:])
    geo = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                       params={"count": 1, "language": "ru", "name": city}).json()
    if not geo.get("results"):
        print("weather: не найден город " + city, file=sys.stderr)
        sys.exit(1)
    p = geo["results"][0]
    place, lat, lon = "%s, %s" % (p["name"], p.get("country", "")), p["latitude"], p["longitude"]
else:
    try:
        lat, lon = kt.js("""() => new Promise((ok, err) => navigator.geolocation.getCurrentPosition(
  (p) => ok([p.coords.latitude, p.coords.longitude]), (e) => err(new Error(e.message)), { timeout: 20000 }))""", timeout=30)
        place = "%.2f, %.2f" % (lat, lon)
    except (kt.JSError, OSError):
        place, lat, lon = "Москва", 55.75, 37.62

r = requests.get("https://api.open-meteo.com/v1/forecast", params={
    "latitude": lat, "longitude": lon, "timezone": "auto",
    "current": "temperature_2m,weather_code,wind_speed_10m",
    "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum,weather_code"}).json()
now, d = r["current"], r["daily"]

print(place)
print("%+.0f°, %s, ветер %.0f км/ч\n" % (now["temperature_2m"], sky(now["weather_code"]), now["wind_speed_10m"]))
lo, hi = min(d["temperature_2m_min"]), max(d["temperature_2m_max"])
W = 24
for day, a, b, rain, code in zip(d["time"], d["temperature_2m_min"], d["temperature_2m_max"],
                                 d["precipitation_sum"], d["weather_code"]):
    x0 = int((a - lo) * W / max(1, hi - lo))
    x1 = max(x0 + 1, int((b - lo) * W / max(1, hi - lo) + 0.5))
    bar = " " * x0 + "\x1b[38;5;%dm%s\x1b[0m" % (color((a + b) / 2), "━" * (x1 - x0)) + " " * (W - x1)
    wet = "%.1f мм" % rain if rain >= 0.1 else ""
    print("%s %s  %+4.0f° %s %+4.0f°  %-9s %s" % (weekday(day), day[8:] + "." + day[5:7], a, bar, b, sky(code), wet))
