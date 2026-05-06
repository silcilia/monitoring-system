import requests
import subprocess
import platform
from datetime import timedelta

from django.utils import timezone

from .models import Service, Log, Contact


# =========================
# CONFIG
# =========================
CHECK_TIMEOUT = 5
RETRY_COUNT = 3
COOLDOWN_MINUTES = 5

FONTE_TOKEN = "token"
FONTE_URL = "https://api.fonnte.com/send"


# =========================
# WHATSAPP SENDER
# =========================
def send_whatsapp(message):
    contacts = Contact.objects.filter(is_active=True)

    for c in contacts:
        try:
            requests.post(
                FONTE_URL,
                data={
                    "target": c.phone_number,
                    "message": message
                },
                headers={
                    "Authorization": FONTE_TOKEN
                },
                timeout=5
            )
        except Exception as e:
            print("WA ERROR:", e)


# =========================
# ALERT FORMAT
# =========================
def send_alert(service, status):
    now = timezone.now().strftime("%d-%m-%Y %H:%M:%S")

    if status == 'DOWN':
        message = f"""🚨 ALERT LAYANAN DOWN
Service : {service.name}
Status  : DOWN
Waktu   : {now}
Reason  : {service.last_down_reason}
"""
    else:
        message = f"""✅ LAYANAN NORMAL
Service : {service.name}
Status  : UP
Waktu   : {now}
"""

    send_whatsapp(message)


# =========================
# HTTP CHECK
# =========================
def check_http(url):
    try:
        res = requests.get(url, timeout=CHECK_TIMEOUT)

        if res.status_code == 200:
            return 'UP', None
        else:
            return 'DOWN', f"HTTP {res.status_code}"

    except requests.exceptions.Timeout:
        return 'DOWN', "Timeout"

    except requests.exceptions.ConnectionError:
        return 'DOWN', "Connection Error"

    except Exception as e:
        return 'DOWN', str(e)


# =========================
# PING CHECK (Linux & Windows)
# =========================
def check_ping(host):
    try:
        param = "-n" if platform.system().lower() == "windows" else "-c"

        result = subprocess.run(
            ["ping", param, "1", host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if result.returncode == 0:
            return 'UP', None
        else:
            return 'DOWN', "Ping gagal"

    except Exception as e:
        return 'DOWN', str(e)


# =========================
# ROUTER CHECK
# =========================
def check_service(service):
    if service.service_type == 'HTTP':
        return check_http(service.url)
    else:
        return check_ping(service.url)


# =========================
# STABLE CHECK (ANTI FALSE ALARM)
# =========================
def stable_check(service):
    results = []
    last_reason = None

    for _ in range(RETRY_COUNT):
        status, reason = check_service(service)
        results.append(status)

        if reason:
            last_reason = reason

    # majority voting
    if results.count('DOWN') > results.count('UP'):
        return 'DOWN', last_reason

    return 'UP', None


# =========================
# COOLDOWN CHECK
# =========================
def can_notify(service):
    if not service.last_notified:
        return True

    return timezone.now() - service.last_notified > timedelta(minutes=COOLDOWN_MINUTES)


# =========================
# MAIN MONITOR LOOP
# =========================
def run_monitoring():
    services = Service.objects.all()

    for s in services:
        try:
            old_status = s.last_status

            # cek service
            new_status, reason = stable_check(s)

            now = timezone.now()

            s.last_checked = now
            s.last_down_reason = reason

            # simpan log
            Log.objects.create(
                service=s,
                status=new_status,
                message=reason
            )

            # kalau status berubah
            if old_status != new_status:

                if can_notify(s):
                    send_alert(s, new_status)
                    s.last_notified = now

                s.last_status = new_status

            s.save()

        except Exception as e:
            print(f"[ERROR] Service {s.name}:", e)