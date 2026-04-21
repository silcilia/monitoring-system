import requests
from .models import Service, Log, ServiceContact
from datetime import datetime


# =========================
# CEK SERVICE (HTTP)
# =========================
def check_service(url):
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return "UP"
        else:
            return "DOWN"
    except:
        return "DOWN"


# =========================
# KIRIM WHATSAPP (FONNTE)
# =========================
def send_whatsapp(message, number):
    url = "https://api.fonnte.com/send"
    headers = {
        "Authorization": "TOKEN_KAMU"  # ganti token kamu
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
# PROSES MONITORING
# =========================
def run_monitoring():
    services = Service.objects.all()

    for service in services:
        status_baru = check_service(service.url)
        status_lama = service.last_status

        print(f"{service.name} | {status_lama} -> {status_baru}")

        # =========================
        # CEK PERUBAHAN STATUS
        # =========================
        if status_baru != status_lama:

            # SIMPAN LOG
            Log.objects.create(
                service=service,
                status=status_baru
            )

            # UPDATE STATUS TERAKHIR
            service.last_status = status_baru
            service.save()

            # FORMAT PESAN
            if status_baru == "DOWN":
                message = f"🚨 ALERT LAYANAN DOWN\nService: {service.name}\nWaktu: {datetime.now()}"
            else:
                message = f"✅ LAYANAN NORMAL\nService: {service.name}\nWaktu: {datetime.now()}"

            # AMBIL CONTACT TERKAIT
            contacts = ServiceContact.objects.filter(service=service)

            # KIRIM KE SEMUA NOMOR
            for sc in contacts:
                if sc.contact.is_active:
                    send_whatsapp(message, sc.contact.phone_number)