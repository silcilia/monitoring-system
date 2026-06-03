import requests
import time
import socket
import urllib3
import warnings
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Contact, Service, NotificationLog
import logging

# ========== MATIKAN WARNING YANG MENGGANGGU ==========
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
warnings.filterwarnings('ignore', category=ResourceWarning)

logger = logging.getLogger(__name__)

# =========================
# KONFIGURASI WHATSAPP (FONNTE)
# =========================
FONTE_TOKEN = settings.FONTE_TOKEN
FONTE_URL = settings.FONTE_API

# =========================
# KONFIGURASI EMAIL
# =========================
EMAIL_FROM = settings.EMAIL_FROM

# =========================
# THRESHOLD DETEKSI LEMOT (detik)
# =========================
SLOW_RESPONSE_THRESHOLD = 3.0

# =========================
# THRESHOLD KONTEN MINIMAL (karakter)
# =========================
MIN_CONTENT_LENGTH = 100

# =========================
# TIMEOUT UNTUK REQUEST (detik)
# =========================
REQUEST_TIMEOUT = 8


# =========================
# CEK KONEKSI INTERNET (GLOBAL)
# =========================
def is_internet_available(host="8.8.8.8", port=53, timeout=3):
    """
    Cek apakah ada koneksi internet
    Returns True jika internet tersedia, False jika tidak
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False


# =========================
# KLASIFIKASI PENYEBAB MASALAH
# =========================
def classify_issue(status_code=None, response_time=None, error_type=None, content_length=None):
    """
    Klasifikasi penyebab masalah untuk WARNING dan DOWN
    
    Returns:
        tuple: (reason_code, reason_detail, tindakan_rekomendasi)
    """
    
    # 0. NO INTERNET - JANGAN DIANGGAP DOWN SERVICE!
    if error_type == 'NO_INTERNET':
        return 'NO_INTERNET', 'Tidak ada koneksi internet - data tidak valid', 'Periksa koneksi jaringan'
    
    # 1. TIMEOUT (Server tidak merespon) -> DOWN
    if error_type == 'Timeout' or (response_time and response_time > 30):
        return 'TIMEOUT', f'Request timeout after {response_time:.2f}s', 'Cek server, restart jika perlu'
    
    # 2. Connection Error (Server mati) -> DOWN
    if error_type == 'ConnectionError':
        return 'CONNECTION_REFUSED', 'Koneksi ditolak - Server mati', 'Cek server, nyalakan jika perlu'
    
    # 3. DNS Error -> DOWN
    if error_type == 'DNS_ERROR':
        return 'DNS_ERROR', 'DNS resolution failed - Domain tidak ditemukan', 'Cek konfigurasi DNS domain'
    
    # 4. SSL Error -> WARNING (server hidup tapi SSL bermasalah)
    if error_type == 'SSL_ERROR':
        return 'SSL_ERROR', 'SSL certificate error - Sertifikat SSL bermasalah', 'Perbarui sertifikat SSL'
    
    # 5. Halaman Kosong -> WARNING
    if content_length is not None and content_length < MIN_CONTENT_LENGTH:
        return 'EMPTY_PAGE', f'Halaman kosong (hanya {content_length} karakter)', 'Cek aplikasi, mungkin error atau maintenance'
    
    # 6. Response Time Lambat -> WARNING
    if response_time and response_time > SLOW_RESPONSE_THRESHOLD:
        return 'SLOW_RESPONSE', f'Response time {response_time:.2f}s (lambat)', 'Optimasi performa server/aplikasi'
    
    # 7. HTTP Status Codes
    if status_code:
        # REDIRECT -> WARNING
        if status_code in [301, 302, 303, 307, 308]:
            return 'REDIRECT', f'URL Redirect ({status_code})', 'Update URL di database dengan URL terbaru'
        
        # 401/403 -> UP (server hidup, perlu login) - BUKAN ERROR
        if status_code in [401, 403]:
            return None, None, None  # Bukan masalah, tetap UP
        
        # 404 -> DOWN
        if status_code == 404:
            return 'HTTP_404', 'Not Found - Halaman tidak ditemukan', 'Perbaiki link atau buat ulang halaman'
        
        # 400, 405, 406, 409, 410 -> DOWN
        if status_code in [400, 405, 406, 409, 410]:
            return f'HTTP_{status_code}', f'Client Error ({status_code})', 'Perbaiki request atau URL'
        
        # 5xx Server Errors -> DOWN
        if 500 <= status_code < 600:
            return f'HTTP_{status_code}', f'Server Error ({status_code})', 'Cek log error server, debug aplikasi'
    
    return 'UNKNOWN', 'Unknown error occurred', 'Cek manual ke server'


# =========================
# CEK STATUS SERVICE (3 STATUS: UP, WARNING, DOWN)
# =========================
def check_service_status(service):
    """
    Mengecek status service dengan 3 status:
    - UP: Service berfungsi normal (200, 401, 403)
    - WARNING: Ada masalah kecil (redirect, kosong, lambat, SSL error)
    - DOWN: Service tidak berfungsi (404, 500, timeout, connection refused)
    """
    
    # ========== CEK INTERNET DULU! ==========
    if not is_internet_available():
        logger.warning(f"Internet TIDAK ADA! Melewati pengecekan {service.name}")
        return None, 0, None, 'NO_INTERNET', 'Tidak ada koneksi internet - data tidak valid'
    
    start_time = time.time()
    status_code = None
    response_time = None
    error_type = None
    content_length = 0
    
    try:
        if service.service_type == 'HTTP':
            response = requests.get(
                service.url,
                timeout=REQUEST_TIMEOUT,
                verify=False,
                allow_redirects=True,
                headers={'User-Agent': 'Monitoring-System/1.0'}
            )
            status_code = response.status_code
            response_time = time.time() - start_time
            content_length = len(response.text.strip())
            
            # REDIRECT -> WARNING
            if status_code in [301, 302, 303, 307, 308]:
                reason, detail, action = classify_issue(status_code=status_code)
                return 'WARNING', response_time, status_code, reason, f"{detail} - Redirect ke: {response.url[:80]}"
            
            # 401/403 -> UP (server hidup, perlu login)
            if status_code in [401, 403]:
                return 'UP', response_time, status_code, None, f"Server hidup - perlu autentikasi ({status_code})"
            
            # 200 OK
            if 200 <= status_code < 300:
                if content_length < MIN_CONTENT_LENGTH:
                    reason, detail, action = classify_issue(content_length=content_length)
                    return 'WARNING', response_time, status_code, reason, detail
                
                if response_time > SLOW_RESPONSE_THRESHOLD:
                    reason, detail, action = classify_issue(response_time=response_time)
                    return 'WARNING', response_time, status_code, reason, detail
                
                return 'UP', response_time, status_code, None, None
            
            # 4xx/5xx -> DOWN
            if status_code >= 400:
                reason, detail, action = classify_issue(status_code=status_code)
                return 'DOWN', response_time, status_code, reason, detail
            
            return 'DOWN', response_time, status_code, 'UNKNOWN', f'Status tidak dikenal ({status_code})'
        
        elif service.service_type == 'PING':
            import subprocess
            import platform
            
            host = service.url.replace('https://', '').replace('http://', '').split('/')[0]
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            result = subprocess.run(
                ['ping', param, '1', host],
                capture_output=True,
                timeout=REQUEST_TIMEOUT
            )
            response_time = time.time() - start_time
            
            if result.returncode == 0:
                if response_time > SLOW_RESPONSE_THRESHOLD:
                    return 'WARNING', response_time, None, 'SLOW_RESPONSE', f'Ping lambat: {response_time:.2f}s'
                return 'UP', response_time, None, None, None
            else:
                return 'DOWN', response_time, None, 'PING_FAILED', 'Host tidak merespon ping'
        
    except requests.exceptions.Timeout:
        response_time = time.time() - start_time
        reason, detail, action = classify_issue(error_type='Timeout', response_time=response_time)
        return 'DOWN', response_time, None, reason, detail
    
    except requests.exceptions.ConnectionError as e:
        response_time = time.time() - start_time
        error_msg = str(e)
        if 'Name or service not known' in error_msg or 'nodename nor servname' in error_msg:
            return 'DOWN', response_time, None, 'DNS_ERROR', 'DNS resolution failed - Domain tidak ditemukan'
        elif 'Connection refused' in error_msg:
            return 'DOWN', response_time, None, 'CONNECTION_REFUSED', 'Koneksi ditolak - Server mati'
        else:
            return 'DOWN', response_time, None, 'NETWORK_UNREACHABLE', error_msg[:200]
    
    except requests.exceptions.SSLError:
        response_time = time.time() - start_time
        reason, detail, action = classify_issue(error_type='SSL_ERROR')
        return 'WARNING', response_time, None, reason, detail
    
    except Exception as e:
        response_time = time.time() - start_time
        return 'DOWN', response_time, None, 'UNKNOWN_ERROR', str(e)[:200]
    
    return 'DOWN', 0, None, 'UNKNOWN', 'Unknown error'


# =========================
# KIRIM WHATSAPP (FONNTE)
# =========================
def send_whatsapp(phone_number, message):
    """Kirim notifikasi via WhatsApp"""
    try:
        response = requests.post(
            FONTE_URL,
            data={
                "target": phone_number,
                "message": message
            },
            headers={
                "Authorization": FONTE_TOKEN
            },
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send WhatsApp to {phone_number}: {e}")
        return False


# =========================
# KIRIM EMAIL
# =========================
def send_email(email_address, subject, message):
    """Kirim notifikasi via Email"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=EMAIL_FROM,
            recipient_list=[email_address],
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {email_address}: {e}")
        return False


# =========================
# KIRIM NOTIFIKASI MULTI-CHANNEL
# =========================
def send_notification(contact, title, message):
    """Kirim notifikasi ke contact berdasarkan channel yang dipilih"""
    results = []
    
    if contact.notification_channel in ['WHATSAPP', 'BOTH']:
        whatsapp_success = send_whatsapp(contact.phone_number, f"{title}\n\n{message}")
        results.append(('WHATSAPP', whatsapp_success))
        
        NotificationLog.objects.create(
            channel='WHATSAPP',
            notification_type=title.split(' - ')[0] if ' - ' in title else 'SERVICE_ALERT',
            recipient=contact.phone_number,
            title=title,
            message=message,
            is_sent=whatsapp_success
        )
    
    if contact.notification_channel in ['EMAIL', 'BOTH']:
        if contact.email:
            email_success = send_email(contact.email, title, message)
            results.append(('EMAIL', email_success))
            
            NotificationLog.objects.create(
                channel='EMAIL',
                notification_type=title.split(' - ')[0] if ' - ' in title else 'SERVICE_ALERT',
                recipient=contact.email,
                title=title,
                message=message,
                is_sent=email_success
            )
    
    return results


# =========================
# KIRIM ALERT (DENGAN ANTI SPAM)
# =========================
def send_alert(service, status, status_code=None, response_time=None, down_reason=None, down_detail=None):
    """Kirim alert ke semua contact yang terhubung dengan service"""
    
    if not is_internet_available():
        logger.info(f"Internet tidak ada! Melewati pengiriman alert untuk {service.name}")
        return
    
    now = timezone.now().strftime("%d-%m-%Y %H:%M:%S")
    
    if not service.needs_notification():
        logger.info(f"Notification cooldown active for service {service.name}")
        return
    
    service.last_notified = timezone.now()
    service.save(update_fields=['last_notified'])
    
    service_contacts = service.servicecontact_set.all()
    
    if not service_contacts.exists():
        logger.warning(f"No contacts found for service {service.name}")
        return
    
    if status == 'DOWN':
        reason_display = {
            'TIMEOUT': '⏱️ Request Timeout - Server tidak merespon',
            'CONNECTION_REFUSED': '🔌 Koneksi Ditolak - Server mati',
            'NETWORK_UNREACHABLE': '🌐 Jaringan Down Total',
            'DNS_ERROR': '🌐 DNS Resolution Failed',
            'HTTP_404': '🔍 Not Found (404) - Halaman tidak ditemukan',
            'HTTP_500': '💥 Internal Server Error (500)',
            'HTTP_502': '⚙️ Bad Gateway (502)',
            'HTTP_503': '⚙️ Service Unavailable (503)',
            'HTTP_504': '⏱️ Gateway Timeout (504)',
            'PING_FAILED': '📡 Host tidak merespon ping',
        }
        
        reason_text = reason_display.get(down_reason, down_reason or 'Unknown Error')
        
        title = f"🔴 ALERT - {service.name} DOWN"
        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━
🔴 SERVICE DOWN ALERT
━━━━━━━━━━━━━━━━━━━━━━━━

📌 Service : {service.name}
🔗 URL : {service.url}
📋 Tipe : {service.service_type}

📊 Detail Masalah:
├ Status : DOWN - Tidak Berfungsi
├ HTTP Code : {status_code or 'N/A'}
├ Response Time : {response_time:.2f}s
└ Penyebab : {reason_text}

📝 Detail : {down_detail or 'Tidak tersedia'}

⏰ Waktu : {now}

━━━━━━━━━━━━━━━━━━━━━━━━
🔧 TINDAKAN: Perbaiki segera!
━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    elif status == 'WARNING':
        title = f"🟠 ALERT - {service.name} WARNING"
        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━
🟠 SERVICE WARNING
━━━━━━━━━━━━━━━━━━━━━━━━

📌 Service : {service.name}
🔗 URL : {service.url}

📊 Detail:
├ Status : WARNING - Perlu Perhatian
├ HTTP Code : {status_code or 'N/A'}
├ Response Time : {response_time:.2f}s
└ Penyebab : {down_detail or down_reason or 'Ada masalah kecil'}

⏰ Waktu : {now}

━━━━━━━━━━━━━━━━━━━━━━━━
🔧 TINDAKAN: Periksa dan perbaiki
━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    else:
        title = f"🟢 RECOVERY - {service.name} Kembali Normal"
        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━
🟢 SERVICE RECOVERY
━━━━━━━━━━━━━━━━━━━━━━━━

📌 Service : {service.name}
🔗 URL : {service.url}

📊 Status:
├ Status : UP - Normal
├ HTTP Code : {status_code or 'N/A'}
└ Response Time : {response_time:.2f}s

⏰ Waktu : {now}

━━━━━━━━━━━━━━━━━━━━━━━━
✅ Layanan telah pulih
━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    for sc in service_contacts:
        contact = sc.contact
        if contact.is_active:
            send_notification(contact, title, message)
            logger.info(f"Alert sent to {contact.name} via {contact.notification_channel}")


# =========================
# KIRIM ALERT DEVICE OFFLINE
# =========================
def send_device_alert(device, is_offline=True):
    """Kirim alert jika ESP32 mati/offline"""
    
    if not is_internet_available():
        logger.info(f"Internet tidak ada! Melewati pengiriman alert device untuk {device.name}")
        return
    
    now = timezone.now().strftime("%d-%m-%Y %H:%M:%S")
    
    device_contacts = device.devicecontact_set.all()
    
    if not device_contacts.exists():
        logger.warning(f"No contacts found for device {device.name}")
        return
    
    if is_offline:
        title = f"🔴 ALERT - Device {device.name} OFFLINE"
        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━
🔴 DEVICE OFFLINE ALERT
━━━━━━━━━━━━━━━━━━━━━━━━

📟 Device : {device.name}
📍 Lokasi : {device.location}

📊 Detail:
├ Status : OFFLINE
├ Last Data : {device.last_seen.strftime('%d-%m-%Y %H:%M:%S') if device.last_seen else 'Tidak pernah'}
└ Power Backup : {'Ada' if device.has_power_backup else 'Tidak Ada'}

⏰ Waktu : {now}

━━━━━━━━━━━━━━━━━━━━━━━━
🔧 TINDAKAN: Cek koneksi dan daya
━━━━━━━━━━━━━━━━━━━━━━━━
"""
    else:
        title = f"🟢 Device {device.name} ONLINE"
        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━
🟢 DEVICE ONLINE
━━━━━━━━━━━━━━━━━━━━━━━━

📟 Device : {device.name}
📍 Lokasi : {device.location}

📊 Status: ONLINE

⏰ Waktu : {now}

━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    for dc in device_contacts:
        contact = dc.contact
        if contact.is_active:
            send_notification(contact, title, message)
            logger.info(f"Device alert sent to {contact.name}")


# =========================
# UPDATE UPTIME PERCENTAGE
# =========================
def update_uptime_percentage(service):
    """Hitung uptime percentage untuk 30 hari terakhir - EXCLUDE data saat internet mati"""
    from datetime import timedelta
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    logs = service.log_set.filter(
        timestamp__gte=thirty_days_ago
    ).exclude(
        down_reason='NO_INTERNET'
    )
    
    total_checks = logs.count()
    if total_checks == 0:
        return
    
    up_checks = logs.filter(status='UP').count()
    uptime = (up_checks / total_checks) * 100
    
    service.uptime_percentage = round(uptime, 2)
    service.save(update_fields=['uptime_percentage'])


# =========================
# CEK STATUS DEVICE (ESP32)
# =========================
def check_device_statuses():
    """Memeriksa status semua device (ESP32)"""
    from .models import Device
    from datetime import timedelta
    
    devices = Device.objects.all()
    offline_threshold = timezone.now() - timedelta(minutes=5)
    
    for device in devices:
        last_log = device.powerlog_set.order_by('-timestamp').first()
        
        if last_log:
            device.last_seen = last_log.timestamp
            device.save(update_fields=['last_seen'])
            
            if last_log.timestamp < offline_threshold:
                if device.status != 'OFFLINE':
                    device.status = 'OFFLINE'
                    device.save(update_fields=['status'])
                    logger.warning(f"Device {device.name} is OFFLINE")
                    try:
                        send_device_alert(device, is_offline=True)
                    except ImportError:
                        pass
            else:
                if device.status != 'ONLINE':
                    device.status = 'ONLINE'
                    device.save(update_fields=['status'])
                    logger.info(f"Device {device.name} is ONLINE")
                    try:
                        send_device_alert(device, is_offline=False)
                    except ImportError:
                        pass


# =========================
# CEK SEMUA SERVICE (UNTUK BACKGROUND THREAD) - TIDAK BUAT LOG JIKA STATUS SAMA
# =========================
def check_all_services():
    """
    Memeriksa semua service dan update status (dijalankan setiap 5 menit)
    - HANYA buat log jika status berubah
    - last_checked SELALU update
    - Notifikasi HANYA jika status berubah
    """
    from .models import Service, Log
    
    if not is_internet_available():
        logger.warning(f"[{timezone.now()}] ⚠️ TIDAK ADA KONEKSI INTERNET! Melewati pengecekan service.")
        return
    
    services = Service.objects.all()
    logger.info(f"[{timezone.now()}] Internet OK, mulai pengecekan {services.count()} service...")
    
    for service in services:
        try:
            status, response_time, status_code, down_reason, down_detail = check_service_status(service)
            
            # Update last_checked (SELALU update)
            service.last_checked = timezone.now()
            service.last_response_time = response_time
            service.last_status_code = status_code
            
            # Cek apakah status BERUBAH
            old_status = service.last_status
            
            if status != old_status:
                # ========== STATUS BERUBAH! ==========
                service.last_status = status
                service.last_down_reason = down_reason
                service.last_down_detail = down_detail
                
                # BUAT LOG BARU (HANYA DISINI!)
                Log.objects.create(
                    service=service,
                    status=status,
                    status_code=status_code,
                    response_time=response_time,
                    down_reason=down_reason,
                    message=down_detail
                )
                
                # Kirim notifikasi jika WARNING atau DOWN
                if status in ['WARNING', 'DOWN']:
                    send_alert(service, status, status_code, response_time, down_reason, down_detail)
                elif status == 'UP' and old_status in ['WARNING', 'DOWN']:
                    send_alert(service, status, status_code, response_time, down_reason, down_detail)
                
                logger.info(f"[AUTO] ✅ {service.name}: {old_status} → {status} (log dibuat)")
            else:
                # ========== STATUS TIDAK BERUBAH! ==========
                # TIDAK buat log, TIDAK kirim notifikasi
                logger.info(f"[AUTO] ⏭️ {service.name}: status tetap {status} (tidak buat log)")
            
            # Update uptime percentage
            update_uptime_percentage(service)
            
            # SELALU simpan (last_checked tetap tersimpan)
            service.save()
            
        except Exception as e:
            logger.error(f"Error checking service {service.name}: {e}")
            
            # Log error (bukan perubahan status)
            Log.objects.create(
                service=service,
                status='UNKNOWN',
                message=f"Monitoring error: {str(e)[:200]}"
            )