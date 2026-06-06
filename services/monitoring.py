from django.utils import timezone
from django.conf import settings
from .models import Service, Contact, Log, Device, PowerLog, NotificationLog
from .utils import (
    check_service_status,
    send_notification,
    update_uptime_percentage,
    is_internet_available
)
import threading
import time
import logging

logger = logging.getLogger(__name__)


# ================================================================
# FUNGSI 1: KIRIM ALERT SERVICE (KE SEMUA CONTACT AKTIF)
# ================================================================
def send_alert(service, status, status_code=None, response_time=None, down_reason=None, down_detail=None):
    """
    Kirim alert ke SEMUA contact yang aktif
    ================================================================
    """
    
    print(f"\n[DEBUG] ========== SEND_ALERT ==========")
    print(f"[DEBUG] Service: {service.name}")
    print(f"[DEBUG] Status: {status}")
    print(f"[DEBUG] Status Code: {status_code}")
    if response_time:
        print(f"[DEBUG] Response Time: {response_time:.2f}s")
    
    if not is_internet_available():
        logger.info(f"Internet tidak ada! Melewati pengiriman alert untuk {service.name}")
        print(f"[DEBUG] Internet TIDAK ADA! Alert dibatalkan.")
        return
    
    now = timezone.now().strftime("%d-%m-%Y %H:%M:%S")
    
    # Update last_notified (untuk record saja)
    service.last_notified = timezone.now()
    service.save(update_fields=['last_notified'])
    
    # Ambil semua contact yang aktif
    contacts = Contact.objects.filter(is_active=True)
    
    if not contacts.exists():
        logger.warning(f"No active contacts found")
        print(f"[DEBUG] Tidak ada contact aktif!")
        return
    
    print(f"[DEBUG] Contact aktif: {contacts.count()} orang")
    
    # ========== FORMAT PESAN BERDASARKAN STATUS ==========
    
    # STATUS DOWN
    if status == 'DOWN':
        if down_reason == 'TIMEOUT':
            tindakan = "⏱️ Server lambat merespon - Cek koneksi server, restart service"
        elif down_reason == 'CONNECTION_REFUSED':
            tindakan = "🔌 Server mati - Restart server atau cek port"
        elif down_reason == 'DNS_ERROR':
            tindakan = "🌐 Cek konfigurasi DNS domain, pastikan domain benar"
        elif down_reason == 'HTTP_404':
            tindakan = "🔍 URL tidak ditemukan - Perbaiki link atau buat ulang halaman"
        elif down_reason == 'HTTP_ERROR' or (status_code and status_code >= 400):
            if status_code == 500:
                tindakan = "💥 Internal Server Error - Cek log error server dan debug aplikasi"
            elif status_code == 502:
                tindakan = "🌉 Bad Gateway - Cek koneksi antara server dan gateway"
            elif status_code == 503:
                tindakan = "🔧 Service Unavailable - Server sedang sibuk atau maintenance"
            elif status_code == 504:
                tindakan = "⏱️ Gateway Timeout - Server upstream terlalu lama merespon"
            else:
                tindakan = f"💥 Error {status_code} - Cek log error server"
        elif down_reason == 'PING_FAILED':
            tindakan = "📡 Host tidak merespon ping - Cek koneksi jaringan, pastikan device menyala"
        else:
            tindakan = "🔧 Cek manual ke server, pastikan service berjalan"
        
        title = f"🔴 DOWN - {service.name}"
        message = f"""🔴 SERVICE DOWN

📌 Nama Service : {service.name}
🔗 Link URL : {service.url}

⚠️ Status : DOWN
📟 Code : {status_code or 'N/A'}
⏱️ Time : {response_time:.2f}s

🔧 TINDAKAN:
{tindakan}

🕐 {now}"""
    
    # STATUS WARNING
    elif status == 'WARNING':
        if down_reason == 'TIMEOUT':
            penyebab = f"Request timeout ({response_time:.2f}s) - Server lambat merespon"
            tindakan = "⏱️ Optimasi performa server, cek koneksi, atau tambah timeout"
        elif down_reason == 'EMPTY_PAGE':
            penyebab = "Halaman kosong (tidak ada konten)"
            tindakan = "📄 Cek aplikasi - Mungkin error atau maintenance, periksa log aplikasi"
        elif down_reason == 'SLOW_RESPONSE':
            penyebab = f"Response time lambat ({response_time:.2f}s)"
            tindakan = "🐌 Optimasi performa - Upgrade server, cache, atau perbaiki query database"
        elif down_reason == 'REDIRECT':
            penyebab = "Terjadi redirect ke URL lain"
            tindakan = "🔄 Update URL di database dengan URL tujuan redirect"
        elif down_reason == 'SSL_ERROR':
            penyebab = "SSL Certificate error atau expired"
            tindakan = "🔒 Perbarui sertifikat SSL, cek masa berlaku"
        else:
            penyebab = down_detail or down_reason or 'Perlu perhatian'
            tindakan = "🔧 Periksa service secara manual"
        
        title = f"🟠 WARNING - {service.name}"
        message = f"""🟠 SERVICE WARNING

📌 Nama Service : {service.name}
🔗 Link URL : {service.url}

⚠️ Status : WARNING
📟 Code : {status_code or 'N/A'}
⏱️ Time : {response_time:.2f}s
💡 Masalah : {penyebab}

🔧 TINDAKAN:
{tindakan}

🕐 {now}"""
    
    # STATUS UP / RECOVERY
    else:  # UP
        title = f"🟢 NORMAL - {service.name}"
        message = f"""🟢 SERVICE NORMAL

📌 Nama Service : {service.name}
🔗 Link URL : {service.url}

✅ Status : UP
📟 Code : {status_code or 'N/A'}
⏱️ Time : {response_time:.2f}s

🕐 {now}"""
    
    # Kirim ke semua contact aktif
    for contact in contacts:
        send_notification(contact, title, message)
        logger.info(f"Alert sent to {contact.name} via {contact.notification_channel}")
        print(f"[DEBUG] ✅ Alert dikirim ke {contact.name} ({contact.phone_number or contact.email})")
    
    print(f"[DEBUG] ==================================\n")


# ================================================================
# FUNGSI 2: KIRIM ALERT DEVICE (ESP32)
# ================================================================
def send_device_alert(device, is_offline=True, extra_messages=None):
    """
    Kirim alert untuk device ESP32 ke SEMUA contact aktif
    ================================================================
    - is_offline=True: ESP32 offline (tidak kirim data >5 menit)
    - is_offline=False + extra_messages: Listrik bermasalah
    - is_offline=False + no extra_messages: Device online normal
    """
    
    print(f"\n[DEBUG] ========== SEND_DEVICE_ALERT ==========")
    print(f"[DEBUG] Device: {device.name}")
    print(f"[DEBUG] is_offline: {is_offline}")
    print(f"[DEBUG] extra_messages: {extra_messages}")
    
    if not is_internet_available():
        logger.info(f"Internet tidak ada! Melewati pengiriman alert device untuk {device.name}")
        print(f"[DEBUG] Internet TIDAK ADA! Alert dibatalkan.")
        return
    
    now = timezone.now().strftime("%d-%m-%Y %H:%M:%S")
    
    # Ambil semua contact aktif
    contacts = Contact.objects.filter(is_active=True)
    
    if not contacts.exists():
        logger.warning(f"No active contacts found")
        print(f"[DEBUG] Tidak ada contact aktif!")
        return
    
    print(f"[DEBUG] Contact aktif: {contacts.count()} orang")
    
    # ========== FORMAT PESAN ==========
    
    if is_offline:
        title = f"🔴 DEVICE OFFLINE - {device.name}"
        message = f"""🚨 ALERT DEVICE OFFLINE

Device : {device.name}
Lokasi : {device.location}
Status : OFFLINE
Waktu : {now}

⚠️ Device tidak mengirim data lebih dari 5 menit!"""
    
    else:
        if extra_messages:
            masalah = "\n".join([f"⚠️ {m}" for m in extra_messages])
            title = f"⚠️ LISTRIK TIDAK STABIL - {device.name}"
            message = f"""⚠️ LISTRIK TIDAK STABIL

Device : {device.name}
Lokasi : {device.location}
{masalah}
Waktu : {now}

🔧 Saran: Cek instalasi listrik, UPS, atau stabilizer"""
        else:
            title = f"🟢 DEVICE ONLINE - {device.name}"
            message = f"""✅ DEVICE NORMAL

Device : {device.name}
Lokasi : {device.location}
Status : ONLINE
Waktu : {now}"""
    
    print(f"[DEBUG] Pesan: {message[:150]}...")
    
    for contact in contacts:
        send_notification(contact, title, message)
        logger.info(f"Device alert sent to {contact.name}")
        print(f"[DEBUG] ✅ Device alert dikirim ke {contact.name}")
    
    print(f"[DEBUG] ========================================\n")


# ================================================================
# FUNGSI 3: CHECK SINGLE SERVICE (UNTUK MANUAL CHECK)
# ================================================================
def check_single_service(service):
    """
    Memeriksa SATU service (manual check)
    - HANYA buat log jika status berubah
    - last_checked SELALU update
    - Notifikasi HANYA jika status berubah (termasuk recovery)
    """
    
    if not is_internet_available():
        print(f"⚠️ Internet TIDAK ADA! Tidak mengecek {service.name}")
        return {
            'success': False,
            'error': 'Tidak ada koneksi internet - cek manual nanti'
        }
    
    try:
        print(f"\n[MANUAL CHECK] ========================================")
        print(f"[MANUAL CHECK] Memulai pengecekan untuk: {service.name}")
        print(f"[MANUAL CHECK] last_checked SEBELUM: {service.last_checked}")
        
        status, response_time, status_code, down_reason, down_detail = check_service_status(service)
        
        print(f"[MANUAL CHECK] Hasil pengecekan: status={status}, response_time={response_time:.2f}s, status_code={status_code}")
        
        # Update last_checked (SELALU update)
        waktu_sekarang = timezone.now()
        service.last_checked = waktu_sekarang
        service.last_response_time = response_time
        service.last_status_code = status_code
        
        print(f"[MANUAL CHECK] last_checked SESUDAH di-set: {service.last_checked}")
        
        old_status = service.last_status
        
        if status != old_status:
            # STATUS BERUBAH!
            service.last_status = status
            service.last_down_reason = down_reason
            service.last_down_detail = down_detail
            
            # BUAT LOG BARU
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
            
            # KIRIM NOTIFIKASI
            if status in ['WARNING', 'DOWN']:
                send_alert(service, status, status_code, response_time, down_reason, down_detail)
                print(f"[MANUAL CHECK] ✅ Alert dikirim: {old_status} → {status} (WARNING/DOWN)")
            elif status == 'UP' and old_status in ['WARNING', 'DOWN']:
                send_alert(service, status, status_code, response_time, down_reason, down_detail)
                print(f"[MANUAL CHECK] ✅ Alert RECOVERY dikirim: {old_status} → {status}")
            
            print(f"[MANUAL CHECK] ✅ {service.name}: {old_status} → {status} (log dibuat)")
        else:
            print(f"[MANUAL CHECK] ⏭️ {service.name}: status tetap {status} (tidak buat log)")
        
        service.save()
        print(f"[MANUAL CHECK] Service {service.name} BERHASIL DISIMPAN")
        
        service.refresh_from_db()
        print(f"[MANUAL CHECK] Verifikasi dari DB: last_checked = {service.last_checked}")
        print(f"[MANUAL CHECK] ========================================\n")
        
        return {
            'success': True,
            'status': status,
            'response_time': response_time,
            'status_code': status_code
        }
        
    except Exception as e:
        print(f"❌ ERROR checking service {service.name}: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            Log.objects.create(
                service=service,
                status='UNKNOWN',
                message=f"Monitoring error: {str(e)[:200]}"
            )
        except:
            pass
        
        return {
            'success': False,
            'error': str(e)
        }


# ================================================================
# FUNGSI 4: CEK STATUS DEVICE (ESP32)
# ================================================================
def check_device_statuses():
    """
    Memeriksa status semua device (ESP32)
    - Jika tidak ada data > 5 menit -> OFFLINE
    - Jika voltage < threshold -> kirim alert listrik tidak stabil
    - Jika current > threshold -> kirim alert listrik tidak stabil
    """
    from datetime import timedelta
    
    devices = Device.objects.all()
    offline_threshold = timezone.now() - timedelta(minutes=5)
    
    for device in devices:
        last_log = device.powerlog_set.order_by('-timestamp').first()
        
        if last_log:
            device.last_seen = last_log.timestamp
            device.save(update_fields=['last_seen'])
            
            # CEK OFFLINE
            if last_log.timestamp < offline_threshold:
                if device.status != 'OFFLINE':
                    device.status = 'OFFLINE'
                    device.save(update_fields=['status'])
                    logger.warning(f"Device {device.name} is OFFLINE")
                    send_device_alert(device, is_offline=True)
            else:
                # DEVICE ONLINE
                if device.status != 'ONLINE':
                    device.status = 'ONLINE'
                    device.save(update_fields=['status'])
                    logger.info(f"Device {device.name} is ONLINE")
                    send_device_alert(device, is_offline=False)
                
                # CEK THRESHOLD (LISTRIK BERMASALAH)
                alert_messages = []
                if device.threshold_voltage and last_log.voltage < device.threshold_voltage:
                    alert_messages.append(f"Voltage : {last_log.voltage}V (Normal: >{device.threshold_voltage}V)")
                
                if device.threshold_current and last_log.current > device.threshold_current:
                    alert_messages.append(f"Arus : {last_log.current}A (Normal: <{device.threshold_current}A)")
                
                if alert_messages:
                    send_device_alert(device, is_offline=False, extra_messages=alert_messages)


# ================================================================
# FUNGSI 5: CEK SEMUA SERVICE (UNTUK BACKGROUND THREAD)
# ================================================================
def check_all_services():
    """
    Memeriksa semua service dan update status (dijalankan setiap 5 menit)
    - HANYA buat log jika status berubah
    - last_checked SELALU update
    - Notifikasi HANYA jika status berubah (termasuk recovery)
    - Juga mengecek status device ESP32
    """
    from .models import Service, Log
    
    if not is_internet_available():
        logger.warning(f"[{timezone.now()}] ⚠️ TIDAK ADA KONEKSI INTERNET! Melewati pengecekan service.")
        return
    
    # ========== CEK SERVICE ==========
    services = Service.objects.all()
    logger.info(f"[{timezone.now()}] Internet OK, mulai pengecekan {services.count()} service...")
    
    for service in services:
        try:
            status, response_time, status_code, down_reason, down_detail = check_service_status(service)
            
            # Update last_checked (SELALU update)
            service.last_checked = timezone.now()
            service.last_response_time = response_time
            service.last_status_code = status_code
            
            is_first_check = service.last_status is None or service.last_status == ''
            old_status = service.last_status
            
            print(f"[AUTO CHECK] {service.name}: old={old_status}, new={status}, first_check={is_first_check}")
            
            if status != old_status or is_first_check:
                service.last_status = status
                service.last_down_reason = down_reason
                service.last_down_detail = down_detail
                
                # BUAT LOG BARU
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
                
                # KIRIM NOTIFIKASI
                if status in ['WARNING', 'DOWN']:
                    print(f"[AUTO CHECK] Mengirim alert karena status {status}")
                    send_alert(service, status, status_code, response_time, down_reason, down_detail)
                elif status == 'UP' and old_status in ['WARNING', 'DOWN']:
                    print(f"[AUTO CHECK] Mengirim alert RECOVERY: {old_status} → {status}")
                    send_alert(service, status, status_code, response_time, down_reason, down_detail)
                
                logger.info(f"[AUTO] ✅ {service.name}: {old_status or 'NEW'} → {status}")
            else:
                logger.info(f"[AUTO] ⏭️ {service.name}: status tetap {status}")
            
            # SELALU simpan
            service.save()
            
        except Exception as e:
            logger.error(f"Error checking service {service.name}: {e}")
            
            try:
                Log.objects.create(
                    service=service,
                    status='UNKNOWN',
                    message=f"Monitoring error: {str(e)[:200]}"
                )
            except:
                pass
    
    # ========== CEK DEVICE ESP32 ==========
    logger.info(f"[{timezone.now()}] Mengecek status device ESP32...")
    try:
        check_device_statuses()
        logger.info(f"[{timezone.now()}] Pengecekan device selesai")
    except Exception as e:
        logger.error(f"Error checking devices: {e}")


# ================================================================
# FUNGSI 6: MONITORING THREAD (UNTUK BACKGROUND TASK)
# ================================================================
monitoring_thread_running = False
monitoring_thread = None

def start_monitoring_thread():
    """Jalankan monitoring di background thread setiap 5 menit"""
    global monitoring_thread_running, monitoring_thread
    
    if monitoring_thread_running:
        print("Monitoring thread already running")
        return
    
    def monitor_loop():
        global monitoring_thread_running
        monitoring_thread_running = True
        print("Monitoring thread loop started")
        
        while monitoring_thread_running:
            try:
                print(f"[{timezone.now()}] Running scheduled monitoring check (5 menit)...")
                check_all_services()
            except Exception as e:
                print(f"Monitoring error: {e}")
                import traceback
                traceback.print_exc()
            
            # Tunggu 5 menit sebelum cek lagi
            for i in range(300):
                if not monitoring_thread_running:
                    break
                time.sleep(1)
        
        print("Monitoring thread loop stopped")
    
    monitoring_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitoring_thread.start()
    print("Monitoring thread started")


def stop_monitoring_thread():
    """Hentikan background monitoring thread"""
    global monitoring_thread_running
    
    if not monitoring_thread_running:
        print("Monitoring thread is not running")
        return
    
    monitoring_thread_running = False
    print("Stopping monitoring thread...")
    
    # Tunggu thread selesai (max 10 detik)
    if monitoring_thread and monitoring_thread.is_alive():
        monitoring_thread.join(timeout=10)
        print("Monitoring thread stopped")