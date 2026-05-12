import requests
import time
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Contact, Service, NotificationLog
import logging

logger = logging.getLogger(__name__)

# =========================
# KONFIGURASI WHATSAPP (FONNTE)
# =========================
FONTE_TOKEN = "token" 
FONTE_URL = "https://api.fonnte.com/send"

# =========================
# KONFIGURASI EMAIL
# =========================
EMAIL_FROM = "jusadvocad1@gmail.com" 

# =========================
# THRESHOLD DETEKSI LEMOT (detik)
# =========================
SLOW_RESPONSE_THRESHOLD = 5.0  

# =========================
# KATEGORI PENYEBAB DOWN
# =========================
def classify_down_reason(status_code=None, response_time=None, error_type=None):
    """
    Klasifikasi penyebab down berdasarkan:
    - status_code: HTTP status code (403, 404, 502, dll)
    - response_time: waktu respon (detik)
    - error_type: jenis error dari requests (Timeout, ConnectionError, dll)
    """
    
    # 1. Timeout (lemot/request terlalu lama)
    if error_type == 'Timeout' or (response_time and response_time > 30):
        return 'TIMEOUT', f'Request timeout after {response_time:.2f}s'
    
    # 2. Connection Error (jaringan down total)
    if error_type == 'ConnectionError':
        return 'CONNECTION_REFUSED', 'Koneksi ditolak atau jaringan down'
    
    # 3. DNS Error
    if error_type == 'DNS_ERROR':
        return 'DNS_ERROR', 'DNS resolution failed'
    
    # 4. SSL Error
    if error_type == 'SSL_ERROR':
        return 'SSL_ERROR', 'SSL certificate verification failed'
    
    # 5. HTTP Status Code berdasarkan RFC 9110
    if status_code:
        if status_code == 400:
            return 'HTTP_400', 'Bad Request - Request tidak valid'
        elif status_code == 401:
            return 'HTTP_401', 'Unauthorized - Akses ditolak'
        elif status_code == 403:
            return 'HTTP_403', 'Forbidden - Akses dilarang'
        elif status_code == 404:
            return 'HTTP_404', 'Not Found - Halaman tidak ditemukan'
        elif status_code == 500:
            return 'HTTP_500', 'Internal Server Error - Error server'
        elif status_code == 502:
            return 'HTTP_502', 'Bad Gateway - Gateway error'
        elif status_code == 503:
            return 'HTTP_503', 'Service Unavailable - Layanan sibuk'
        elif status_code == 504:
            return 'HTTP_504', 'Gateway Timeout - Gateway timeout'
        elif 500 <= status_code < 600:
            return 'HTTP_500', f'Server Error ({status_code})'
        elif 400 <= status_code < 500:
            return f'HTTP_{status_code}', f'Client Error ({status_code})'
    
    return 'UNKNOWN_ERROR', 'Unknown error occurred'


# =========================
# CEK STATUS SERVICE (DENGAN DETEKSI LENGKAP)
# =========================
def check_service_status(service):
    """
    Mengecek status service dengan deteksi:
    - Response time (deteksi lemot)
    - HTTP Status Code (klasifikasi error)
    - Koneksi (down total)
    """
    start_time = time.time()
    status_code = None
    response_time = None
    error_type = None
    down_reason = None
    down_detail = None
    
    try:
        if service.service_type == 'HTTP':
            # 🔥 HEAD REQUEST lebih ringan, tapi bisa juga GET
            response = requests.get(
                service.url,
                timeout=10,  # timeout 10 detik
                verify=False,  # abaikan SSL untuk sementara
                allow_redirects=True
            )
            status_code = response.status_code
            response_time = time.time() - start_time
            
            # DETEKSI LEMOT (response time > threshold)
            if response_time > SLOW_RESPONSE_THRESHOLD:
                return 'DEGRADED', response_time, status_code, 'TIMEOUT', f'Response slow: {response_time:.2f}s'
            
            # DETEKSI HTTP STATUS CODE
            if 200 <= status_code < 300:
                return 'UP', response_time, status_code, None, None
            else:
                reason, detail = classify_down_reason(status_code=status_code)
                return 'DOWN', response_time, status_code, reason, detail
        
        elif service.service_type == 'PING':
            # UNTUK PING
            import subprocess
            import platform
            
            # Extract hostname from URL
            host = service.url.replace('https://', '').replace('http://', '').split('/')[0]
            
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            result = subprocess.run(
                ['ping', param, '1', host],
                capture_output=True,
                timeout=5
            )
            response_time = time.time() - start_time
            
            if result.returncode == 0:
                if response_time > SLOW_RESPONSE_THRESHOLD:
                    return 'DEGRADED', response_time, None, 'TIMEOUT', f'Ping slow: {response_time:.2f}s'
                return 'UP', response_time, None, None, None
            else:
                return 'DOWN', response_time, None, 'NETWORK_UNREACHABLE', 'Ping failed - Host unreachable'
        
    except requests.exceptions.Timeout:
        response_time = time.time() - start_time
        return 'DOWN', response_time, None, 'TIMEOUT', f'Request timeout after {response_time:.2f}s'
    
    except requests.exceptions.ConnectionError as e:
        response_time = time.time() - start_time
        error_msg = str(e)
        if 'Name or service not known' in error_msg or 'nodename nor servname' in error_msg:
            return 'DOWN', response_time, None, 'DNS_ERROR', 'DNS resolution failed'
        elif 'Connection refused' in error_msg:
            return 'DOWN', response_time, None, 'CONNECTION_REFUSED', 'Koneksi ditolak'
        else:
            return 'DOWN', response_time, None, 'NETWORK_UNREACHABLE', error_msg[:200]
    
    except requests.exceptions.SSLError:
        response_time = time.time() - start_time
        return 'DOWN', response_time, None, 'SSL_ERROR', 'SSL certificate error'
    
    except Exception as e:
        response_time = time.time() - start_time
        return 'DOWN', response_time, None, 'UNKNOWN_ERROR', str(e)[:200]


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
            }
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
    """
    Kirim notifikasi ke contact berdasarkan channel yang dipilih
    """
    results = []
    
    if contact.notification_channel in ['WHATSAPP', 'BOTH']:
        whatsapp_success = send_whatsapp(contact.phone_number, f"{title}\n\n{message}")
        results.append(('WHATSAPP', whatsapp_success))
        
        # Simpan ke NotificationLog
        NotificationLog.objects.create(
            channel='WHATSAPP',
            notification_type=title.split(' - ')[0] if ' - ' in title else 'SERVICE_DOWN',
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
                notification_type=title.split(' - ')[0] if ' - ' in title else 'SERVICE_DOWN',
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
    """
    Kirim alert ke semua contact yang terhubung dengan service.
    Dilengkapi anti spam berdasarkan cooldown.
    """
    now = timezone.now().strftime("%d-%m-%Y %H:%M:%S")
    
    # KIRIM NOTIFIKASI (ANTI SPAM)
    if not service.needs_notification():
        logger.info(f"Notification cooldown active for service {service.name}")
        return
    
    # UPDATE last_notified
    service.last_notified = timezone.now()
    service.save(update_fields=['last_notified'])
    
    # Ambil semua contact yang terhubung dengan service ini
    service_contacts = service.servicecontact_set.all()
    
    if not service_contacts.exists():
        logger.warning(f"No contacts found for service {service.name}")
        return
    
    # PESAN BERDASARKAN STATUS
    if status == 'DOWN':
        # Peta readable reason
        reason_display = {
            'TIMEOUT': '⏱️ Request Timeout (Server tidak merespon)',
            'CONNECTION_REFUSED': '🔌 Koneksi Ditolak',
            'NETWORK_UNREACHABLE': '🌐 Jaringan Down Total',
            'DNS_ERROR': '🌐 DNS Resolution Failed',
            'SSL_ERROR': '🔒 SSL Certificate Error',
            'HTTP_403': '🚫 Forbidden (403) - Akses dilarang',
            'HTTP_404': '🔍 Not Found (404) - Halaman tidak ditemukan',
            'HTTP_502': '⚙️ Bad Gateway (502) - Gateway error',
            'HTTP_503': '⚙️ Service Unavailable (503)',
            'HTTP_504': '⏱️ Gateway Timeout (504)',
            'HTTP_400': '❌ Bad Request (400)',
            'HTTP_401': '🔐 Unauthorized (401)',
        }
        
        reason_text = reason_display.get(down_reason, down_reason or 'Unknown Error')
        
        title = f"🚨 ALERT - {service.name} DOWN"
        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  SERVICE DOWN ALERT
━━━━━━━━━━━━━━━━━━━━━━━━

📌 Service : {service.name}
🔗 URL : {service.url}
📋 Tipe : {service.service_type}

📊 Detail Masalah:
├ Status : DOWN
├ HTTP Code : {status_code or 'N/A'}
├ Response Time : {response_time:.2f}s jika ada)
└ Penyebab : {reason_text}

📝 Detail : {down_detail or 'Tidak tersedia'}

⏰ Waktu : {now}

━━━━━━━━━━━━━━━━━━━━━━━━
✅ Aksi: Tim akan melakukan pengecekan
━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    elif status == 'DEGRADED':
        title = f"⚠️ ALERT - {service.name} DEGRADED (Lemot)"
        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  SERVICE DEGRADED ALERT
━━━━━━━━━━━━━━━━━━━━━━━━

📌 Service : {service.name}
🔗 URL : {service.url}

📊 Detail:
├ Status : DEGRADED (Lambat)
├ Response Time : {response_time:.2f} detik
├ Threshold Normal : < 5 detik
└ Rekomendasi : Periksa jaringan server

⏰ Waktu : {now}

━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    else:  # UP / RECOVER
        title = f"✅ RECOVERY - {service.name} Kembali Normal"
        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━
✅  SERVICE RECOVERY
━━━━━━━━━━━━━━━━━━━━━━━━

📌 Service : {service.name}
🔗 URL : {service.url}

📊 Status:
├ Status : UP (Normal)
├ HTTP Code : {status_code or 'N/A'}
├ Response Time : {response_time:.2f}s
└ Kondisi : Layanan telah pulih

⏰ Waktu : {now}

━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    # KIRIM KE SEMUA CONTACT
    for sc in service_contacts:
        contact = sc.contact
        if contact.is_active:
            send_notification(contact, title, message)
            logger.info(f"Alert sent to {contact.name} via {contact.notification_channel}")


# =========================
# KIRIM ALERT DEVICE OFFLINE (ESP32 MATI)
# =========================
def send_device_alert(device, is_offline=True):
    """Kirim alert jika ESP32 mati/offline"""
    now = timezone.now().strftime("%d-%m-%Y %H:%M:%S")
    
    # Ambil contact yang terhubung dengan device
    device_contacts = device.devicecontact_set.all()
    
    if not device_contacts.exists():
        logger.warning(f"No contacts found for device {device.name}")
        return
    
    if is_offline:
        title = f"🔌 ALERT - Device {device.name} OFFLINE"
        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━
🔌  DEVICE OFFLINE ALERT
━━━━━━━━━━━━━━━━━━━━━━━━

📟 Device : {device.name}
📍 Lokasi : {device.location}

📊 Detail:
├ Status : OFFLINE
├ Last Data : {device.last_seen.strftime('%d-%m-%Y %H:%M:%S') if device.last_seen else 'Tidak pernah'}
├ Power Backup : {'Ada' if device.has_power_backup else 'Tidak Ada'}
└ Rekomendasi : Cek koneksi dan daya

⏰ Waktu : {now}

━━━━━━━━━━━━━━━━━━━━━━━━
"""
    else:
        title = f"✅ Device {device.name} ONLINE"
        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━
✅  DEVICE ONLINE
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
    """Hitung uptime percentage untuk 30 hari terakhir"""
    from datetime import timedelta
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    logs = service.log_set.filter(timestamp__gte=thirty_days_ago)
    
    total_checks = logs.count()
    if total_checks == 0:
        return
    
    up_checks = logs.filter(status='UP').count()
    uptime = (up_checks / total_checks) * 100
    
    service.uptime_percentage = round(uptime, 2)
    service.save(update_fields=['uptime_percentage'])

# utils.py - Tambahkan fungsi ini jika belum ada

def check_device_statuses():
    """Memeriksa status semua device (ESP32)"""
    from .models import Device
    from django.utils import timezone
    from datetime import timedelta
    import logging
    
    logger = logging.getLogger(__name__)
    
    devices = Device.objects.all()
    offline_threshold = timezone.now() - timedelta(minutes=5)  # 5 menit offline
    
    for device in devices:
        # Cek apakah device masih online
        last_log = device.powerlog_set.order_by('-timestamp').first()
        
        if last_log:
            device.last_seen = last_log.timestamp
            device.save(update_fields=['last_seen'])
            
            if last_log.timestamp < offline_threshold:
                if device.status != 'OFFLINE':
                    device.status = 'OFFLINE'
                    device.save(update_fields=['status'])
                    logger.warning(f"Device {device.name} is OFFLINE (no data for >5 minutes)")
                    # Kirim notifikasi device offline jika perlu
                    try:
                        from .utils import send_device_alert
                        send_device_alert(device, is_offline=True)
                    except ImportError:
                        pass
            else:
                if device.status != 'ONLINE':
                    device.status = 'ONLINE'
                    device.save(update_fields=['status'])
                    logger.info(f"Device {device.name} is ONLINE again")
                    try:
                        from .utils import send_device_alert
                        send_device_alert(device, is_offline=False)
                    except ImportError:
                        pass


def check_all_services():
    """Memeriksa semua service dan update status"""
    from .models import Service, Log
    from django.utils import timezone
    import logging
    
    logger = logging.getLogger(__name__)
    
    services = Service.objects.all()
    
    for service in services:
        try:
            status, response_time, status_code, down_reason, down_detail = check_service_status(service)
            
            # Update last_checked
            service.last_checked = timezone.now()
            service.last_response_time = response_time
            service.last_status_code = status_code
            
            # Cek apakah status berubah
            old_status = service.last_status
            
            if status != old_status:
                service.last_status = status
                service.last_down_reason = down_reason
                service.last_down_detail = down_detail
                
                # Simpan ke log
                Log.objects.create(
                    service=service,
                    status=status,
                    status_code=status_code,
                    response_time=response_time,
                    down_reason=down_reason,
                    message=down_detail
                )
                
                # Kirim notifikasi jika DOWN atau DEGRADED
                if status in ['DOWN', 'DEGRADED']:
                    send_alert(service, status, status_code, response_time, down_reason, down_detail)
                elif status == 'UP' and old_status in ['DOWN', 'DEGRADED']:
                    # Kirim notifikasi recovery
                    send_alert(service, status, status_code, response_time, down_reason, down_detail)
                
                logger.info(f"Service {service.name} status changed: {old_status} -> {status}")
            else:
                # Status tidak berubah, tetap update log jika perlu (opsional)
                if status == 'DOWN' or status == 'DEGRADED':
                    Log.objects.create(
                        service=service,
                        status=status,
                        status_code=status_code,
                        response_time=response_time,
                        down_reason=down_reason,
                        message=down_detail
                    )
            
            # Update uptime percentage
            update_uptime_percentage(service)
            
            service.save()
            
        except Exception as e:
            logger.error(f"Error checking service {service.name}: {e}")
            
            # Log error
            Log.objects.create(
                service=service,
                status='UNKNOWN',
                message=f"Monitoring error: {str(e)[:200]}"
            )