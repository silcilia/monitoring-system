import requests
from django.utils import timezone
from .models import Contact

FONTE_TOKEN = "jus"
FONTE_URL = "https://api.fonnte.com/send"


def send_whatsapp(message):
    contacts = Contact.objects.filter(is_active=True)

    for c in contacts:
        requests.post(
            FONTE_URL,
            data={
                "target": c.phone_number,
                "message": message
            },
            headers={
                "Authorization": FONTE_TOKEN
            }
        )


def send_alert(service, status):
    now = timezone.now().strftime("%d-%m-%Y %H:%M:%S")

    if status == 'DOWN':
        msg = f"""🚨 ALERT LAYANAN DOWN
Service : {service.name}
Status : DOWN
Waktu : {now}
Reason : {service.last_down_reason}
"""
    else:
        msg = f"""✅ LAYANAN NORMAL
Service : {service.name}
Status : UP
Waktu : {now}
"""

    send_whatsapp(msg)