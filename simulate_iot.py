import requests
import random
import time

URL = "http://127.0.0.1:8000/api/power/"

while True:
    data = {
        "device_id": 1,
        "voltage": random.randint(180, 240),
        "current": round(random.uniform(0.5, 3.0), 2),
        "power": random.randint(50, 500)
    }

    requests.post(URL, json=data)
    print("Kirim:", data)

    time.sleep(5)