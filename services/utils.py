import requests
import time
import socket
import urllib3
import warnings
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Contact, NotificationLog
import logging

# ================================================================
# KONFIGURASI AWAL & MATIKAN WARNING
# ================================================================

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

logger = logging.getLogger(__name__)

# ================================================================
# KONFIGURASI WHATSAPP (FONNTE)
# ================================================================
FONTE_TOKEN = #"KMruNFCaPo9EdbMw9QA6"
FONTE_URL = #"https://api.fonnte.com/send"

# ================================================================
# KONFIGURASI EMAIL
# ================================================================
EMAIL_FROM = #"rsiadw45@gmail.com"

# ================================================================
# THRESHOLD DAN BATASAN
# ================================================================
SLOW_RESPONSE_THRESHOLD = 10.0       # Batas response lambat (detik)
MIN_CONTENT_LENGTH = 100             # Batas konten minimal (karakter)
REQUEST_TIMEOUT = 10                 # Timeout request HTTP (detik)

# ================================================================
# KONFIGURASI UPTIME CALCULATION (BOBOT STATUS)
# ================================================================
# Bobot untuk menghitung uptime percentage
# UP = 100% (service normal)
# WARNING = 70% (service bermasalah tapi masih bisa diakses)
# DOWN = 0% (service mati total)
# ================================================================
WEIGHT_UP = 100       # Service normal sempurna
WEIGHT_WARNING = 70   # Service bermasalah tapi masih jalan (bisa diubah)
WEIGHT_DOWN = 0       # Service mati total
WEIGHT_UNKNOWN = 0    # Status tidak dikenal


# ================================================================
# FUNGSI 1: CEK KONEKSI INTERNET
# ================================================================
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


# ================================================================
# FUNGSI 2: KLASIFIKASI PENYEBAB MASALAH
# ================================================================
def classify_issue(status_code=None, response_time=None, error_type=None, content_length=None):
    """
    Klasifikasi penyebab masalah untuk menentukan status WARNING atau DOWN
    
    Returns:
        tuple: (reason_code, reason_detail, tindakan_rekomendasi)
    """
    
    # 0. NO INTERNET - BUKAN ERROR SERVICE!
    if error_type == 'NO_INTERNET':
        return 'NO_INTERNET', 'Tidak ada koneksi internet - data tidak valid', 'Periksa koneksi jaringan'
    
    # 1. TIMEOUT -> WARNING (server masih hidup tapi lambat)
    if error_type == 'Timeout' or (response_time and response_time > 30):
        return 'TIMEOUT', f'Request timeout after {response_time:.2f}s', 'Server lambat, cek koneksi atau optimasi performa'
    
    # 2. Connection Error -> DOWN (server mati)
    if error_type == 'ConnectionError':
        return 'CONNECTION_REFUSED', 'Koneksi ditolak - Server mati', 'Cek server, nyalakan jika perlu'
    
    # 3. DNS Error -> DOWN (domain tidak ditemukan)
    if error_type == 'DNS_ERROR':
        return 'DNS_ERROR', 'DNS resolution failed - Domain tidak ditemukan', 'Cek konfigurasi DNS domain'
    
    # 4. SSL Error -> WARNING (sertifikat bermasalah)
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
        # REDIRECT (301,302,dll) -> WARNING
        if status_code in [301, 302, 303, 307, 308]:
            return 'REDIRECT', f'URL Redirect ({status_code})', 'Update URL di database dengan URL terbaru'
        
        # 401/403 -> UP (server hidup, perlu login) - BUKAN ERROR!
        if status_code in [401, 403]:
            return None, None, None
        
        # 404 -> DOWN
        if status_code == 404:
            return 'HTTP_404', 'Not Found - Halaman tidak ditemukan', 'Perbaiki link atau buat ulang halaman'
        
        # 4xx Lainnya -> DOWN
        if status_code in [400, 405, 406, 409, 410]:
            return f'HTTP_{status_code}', f'Client Error ({status_code})', 'Perbaiki request atau URL'
        
        # 5xx Server Errors -> DOWN
        if 500 <= status_code < 600:
            return f'HTTP_{status_code}', f'Server Error ({status_code})', 'Cek log error server, debug aplikasi'
    
    return 'UNKNOWN', 'Unknown error occurred', 'Cek manual ke server'


# ================================================================
# FUNGSI 3: CEK STATUS SERVICE (HTTP / PING)
# ================================================================
def check_service_status(service):
    """
    Mengecek status service dengan 3 status: UP, WARNING, DOWN
    
    Returns:
        tuple: (status, response_time, status_code, down_reason, down_detail)
    """
    
    # CEK INTERNET DULU!
    if not is_internet_available():
        logger.warning(f"Internet TIDAK ADA! Melewati pengecekan {service.name}")
        return None, 0, None, 'NO_INTERNET', 'Tidak ada koneksi internet - data tidak valid'
    
    start_time = time.time()
    status_code = None
    response_time = None
    content_length = 0
    
    try:
        # ========== UNTUK SERVICE HTTP ==========
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
            
            # 200 OK - cek konten dan kecepatan
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
                if status_code == 404:
                    return 'DOWN', response_time, status_code, 'HTTP_404', 'Halaman tidak ditemukan'
                return 'DOWN', response_time, status_code, 'HTTP_ERROR', f'Error {status_code}'
            
            return 'DOWN', response_time, status_code, 'UNKNOWN', f'Status tidak dikenal ({status_code})'
        
        # ========== UNTUK SERVICE PING ==========
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
        return 'WARNING', response_time, None, 'TIMEOUT', f'Request timeout - Server lambat merespon ({response_time:.2f}s)'
    
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


# ================================================================
# FUNGSI 4: KIRIM WHATSAPP VIA FONNTE
# ================================================================
def send_whatsapp(phone_number, message):
    """
    Kirim notifikasi via WhatsApp menggunakan API Fonnte
    Returns True jika berhasil, False jika gagal
    """
    try:
        phone = phone_number.strip()
        if phone.startswith('0'):
            phone = '62' + phone[1:]
        elif phone.startswith('+'):
            phone = phone[1:]
        
        print(f"[WA] Mengirim ke: {phone}")
        
        response = requests.post(
            FONTE_URL,
            data={"target": phone, "message": message},
            headers={"Authorization": FONTE_TOKEN},
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"[WA] Berhasil dikirim ke {phone}")
            return True
        else:
            print(f"[WA] Gagal: {response.text}")
            return False
            
    except Exception as e:
        print(f"[WA] Error: {e}")
        return False


# ================================================================
# FUNGSI 5: KIRIM EMAIL
# ================================================================
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
        print(f"[EMAIL] Berhasil dikirim ke {email_address}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {email_address}: {e}")
        return False


# ================================================================
# FUNGSI 6: KIRIM NOTIFIKASI MULTI-CHANNEL
# ================================================================
def send_notification(contact, title, message):
    """
    Kirim notifikasi ke contact berdasarkan channel yang dipilih
    Channel: WHATSAPP, EMAIL, BOTH
    """
    results = []
    
    if contact.notification_channel in ['WHATSAPP', 'BOTH']:
        whatsapp_success = send_whatsapp(contact.phone_number, message)
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


# ================================================================
# FUNGSI 7:  UPTIME PERCENTAGE 
# ================================================================
def update_uptime_percentage(service):
    from datetime import timedelta
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    # Ambil log 30 hari terakhir (abaikan log karena NO_INTERNET)
    logs = service.log_set.filter(
        timestamp__gte=thirty_days_ago
    ).exclude(
        down_reason='NO_INTERNET'
    )
    
    total_checks = logs.count()
    if total_checks == 0:
        return
    
    # Hitung total bobot berdasarkan status
    total_weight = 0
    for log in logs:
        if log.status == 'UP':
            total_weight += WEIGHT_UP
        elif log.status == 'WARNING':
            total_weight += WEIGHT_WARNING
        elif log.status == 'DOWN':
            total_weight += WEIGHT_DOWN
        else:
            # Status UNKNOWN atau lainnya
            total_weight += WEIGHT_UNKNOWN
    
    # Rata-rata bobot = uptime percentage
    uptime = (total_weight / total_checks)
    
    # Simpan ke database
    service.uptime_percentage = round(uptime, 2)
    service.save(update_fields=['uptime_percentage'])
    
    # Debug output (opsional, bisa dihapus jika tidak perlu)
    logger.debug(f"Uptime calculation for {service.name}: "
                 f"total={total_checks}, "
                 f"UP={logs.filter(status='UP').count()}, "
                 f"WARNING={logs.filter(status='WARNING').count()}, "
                 f"DOWN={logs.filter(status='DOWN').count()}, "
                 f"uptime={uptime:.2f}%")


# ================================================================
# FUNGSI 8: GET UPTIME WITH WEIGHT (UNTUK REPORTING)
# ================================================================
def get_weighted_uptime(service, days=30):
    """
    Mendapatkan uptime percentage dengan bobot untuk periode tertentu
    ================================================================
    Args:
        service: objek Service
        days: jumlah hari kebelakang (default 30)
    
    Returns:
        float: uptime percentage (0-100)
    """
    from datetime import timedelta
    
    since = timezone.now() - timedelta(days=days)
    
    logs = service.log_set.filter(
        timestamp__gte=since
    ).exclude(
        down_reason='NO_INTERNET'
    )
    
    total_checks = logs.count()
    if total_checks == 0:
        return 100.0  # Belum ada data, anggap 100%
    
    total_weight = 0
    for log in logs:
        if log.status == 'UP':
            total_weight += WEIGHT_UP
        elif log.status == 'WARNING':
            total_weight += WEIGHT_WARNING
        elif log.status == 'DOWN':
            total_weight += WEIGHT_DOWN
        else:
            total_weight += WEIGHT_UNKNOWN
    
    return round((total_weight / total_checks), 2)


def get_sla_status(uptime):
    """
    Mendapatkan status SLA berdasarkan uptime percentage
    ================================================================
    Returns:
        str: 'Good', 'Warning', atau 'Critical'
    """
    if uptime >= 99.0:
        return 'Excellent'
    elif uptime >= 95.0:
        return 'Good'
    elif uptime >= 90.0:
        return 'Fair'
    elif uptime >= 80.0:
        return 'Warning'
    else:
        return 'Critical'