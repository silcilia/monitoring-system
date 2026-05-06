import requests
from datetime import datetime
from .models import (
    Service, Log, ServiceContact,
    Device, PowerLog, DeviceContact
)

# =========================
# CEK SERVICE
# =========================
def check_service(url):
    try:
        response = requests.get(url, timeout=5)
        return "UP" if response.status_code == 200 else "DOWN"
    except:
        return "DOWN"


# =========================
# KIRIM WA
# =========================
def send_whatsapp(message, number):
    url = "https://api.fonnte.com/send"
    headers = {
        "Authorization": "KMruNFCaPo9EdbMw9QA6"
    }

    data = {
        "target": number,
        "message": message
    }

    try:
        requests.post(url, headers=headers, data=data)
    except:
        print("Gagal kirim WA")


# =========================
# MONITOR SERVICE
# =========================
def run_service_monitoring():
    services = Service.objects.all()

    for service in services:
        status_baru = check_service(service.url)
        status_lama = service.last_status

        print(f"{service.name} | {status_lama} -> {status_baru}")

        if status_baru != status_lama:

            Log.objects.create(service=service, status=status_baru)

            service.last_status = status_baru
            service.save()

            if status_baru == "DOWN":
                message = f"🚨 SERVICE DOWN\n{service.name}\n{datetime.now()}"
            else:
                message = f"✅ SERVICE NORMAL\n{service.name}\n{datetime.now()}"

            contacts = ServiceContact.objects.filter(service=service)

            for sc in contacts:
                if sc.contact.is_active:
                    send_whatsapp(message, sc.contact.phone_number)


# =========================
# MONITOR POWER (IOT)
# =========================
def run_power_monitoring():
    devices = Device.objects.all()

    for device in devices:
        last_log = PowerLog.objects.filter(device=device).last()

        if not last_log:
            continue

        alert = False
        message = ""

        if last_log.voltage < device.threshold_voltage:
            alert = True
            message += "⚡ Voltage Drop\n"

        if last_log.current > device.threshold_current:
            alert = True
            message += "🔥 Arus Tinggi\n"

        if alert:
            message += f"""
Device: {device.name}
Voltage: {last_log.voltage}V
Current: {last_log.current}A
Time: {datetime.now()}
"""

            contacts = DeviceContact.objects.filter(device=device)

            for dc in contacts:
                if dc.contact.is_active:
                    send_whatsapp(message, dc.contact.phone_number)


# =========================
# JALANKAN SEMUA
# =========================
def run_all_monitoring():
    print("=== SERVICE ===")
    run_service_monitoring()

    print("=== POWER ===")
    run_power_monitoring()