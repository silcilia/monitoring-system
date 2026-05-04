import requests
import random
import time

# ========================
# KONFIGURASI
# ========================
URL = "http://127.0.0.1:8000/api/power-add/"

API_KEY = "jusavocad"

HEADERS = {
    "X-API-KEY": API_KEY,
    "Content-Type": "application/json"
}

DEVICE_ID = 1 

print("=" * 60)
print("Memulai pengiriman data ke Monitoring System")
print(f"URL: {URL}")
print(f"API Key: {API_KEY}")
print(f"Device ID: {DEVICE_ID}")
print("=" * 60)
print()

count = 0
success = 0
failed = 0

while True:
    count += 1
    data = {
        "device_id": DEVICE_ID,
        "voltage": random.randint(180, 240),
        "current": round(random.uniform(0.5, 3.0), 2),
        "power": random.randint(50, 500)
    }

    try:
        response = requests.post(URL, json=data, headers=HEADERS)
        
        print(f"[{count}] 📤 Mengirim: {data['voltage']}V, {data['current']}A, {data['power']}W")
        
        if response.status_code == 201:
            success += 1
            result = response.json()
            print(f"    ✅ Berhasil! Device: {result.get('device_name', 'Unknown')}")
        elif response.status_code == 403:
            failed += 1
            print(f"    ❌ Unauthorized! Periksa API Key")
            print(f"    Response: {response.text}")
        elif response.status_code == 400:
            failed += 1
            print(f"    ❌ Bad Request: {response.text}")
        else:
            failed += 1
            print(f"    ❌ Gagal (HTTP {response.status_code}): {response.text}")
            
    except requests.exceptions.ConnectionError:
        failed += 1
        print(f"[{count}] ❌ Error: Tidak dapat terhubung ke server. Pastikan Django running!")
    except Exception as e:
        failed += 1
        print(f"[{count}] ❌ Error: {e}")
    
    # Tampilkan statistik setiap 10 data
    if count % 10 == 0:
        print(f"\n📊 STATISTIK: Total={count}, Sukses={success}, Gagal={failed}")
        print(f"   Success Rate: {(success/count)*100:.1f}%\n")
    
    print()
    time.sleep(5)