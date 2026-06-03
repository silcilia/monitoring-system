from django.views.generic import ListView, CreateView, TemplateView, UpdateView
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict
from django.http import JsonResponse
from django.core.management import call_command
from django.db.models import Q
import threading
from django.conf import settings

import time
from .utils import (
    check_service_status,
    send_alert,
    update_uptime_percentage,
    is_internet_available,
    send_device_alert  # Tambahkan import ini
)

from .models import Service, Contact, PowerLog, Log, Device, ServiceContact, DeviceContact, NotificationLog

# ======================
# AUTH DJANGO
# ======================
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout

# ======================
# CSRF & JSON
# ======================
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
import json

# ======================
# IMPORT UTILS
# ======================
from .utils import check_service_status, send_alert, update_uptime_percentage, is_internet_available, send_device_alert


# ======================
# HELPER DASHBOARD
# ======================
def get_dashboard_data():
    services = Service.objects.all()

    total = services.count()
    up = services.filter(last_status='UP').count()
    warning = services.filter(last_status='WARNING').count()
    down = services.filter(last_status='DOWN').count()

    percent = int((up / total) * 100) if total > 0 else 0

    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=6)

    logs = Log.objects.filter(timestamp__date__gte=seven_days_ago)

    daily = defaultdict(list)

    for log in logs:
        day = log.timestamp.date()
        daily[day].append(log.status)

    labels = []
    data = []

    for i in range(7):
        day = seven_days_ago + timedelta(days=i)
        statuses = daily.get(day, [])

        if statuses:
            up_count = statuses.count('UP')
            percent_day = int((up_count / len(statuses)) * 100)
        else:
            percent_day = 100

        labels.append(day.strftime("%a"))
        data.append(percent_day)

    return {
        'total': total,
        'up': up,
        'warning': warning,
        'down': down,
        'percent': percent,
        'labels': labels,
        'data': data,
    }


# ======================
# FUNGSI CHECK SINGLE SERVICE (UNTUK MANUAL CHECK) - DIPERBAIKI
# ======================
def check_single_service(service):
    """
    Memeriksa SATU service (manual check)
    - HANYA buat log jika status berubah
    - last_checked SELALU update
    - Notifikasi HANYA jika status berubah
    """
    
    # ========== CEK INTERNET DULU! ==========
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
        
        # ========== UPDATE last_checked (SELALU update) ==========
        waktu_sekarang = timezone.now()
        service.last_checked = waktu_sekarang
        service.last_response_time = response_time
        service.last_status_code = status_code
        
        print(f"[MANUAL CHECK] last_checked SESUDAH di-set: {service.last_checked}")
        
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
            
            # Update uptime percentage
            update_uptime_percentage(service)
            
            # Kirim notifikasi jika WARNING atau DOWN
            if status in ['WARNING', 'DOWN']:
                send_alert(service, status, status_code, response_time, down_reason, down_detail)
            
            print(f"[MANUAL CHECK] ✅ {service.name}: {old_status} → {status} (log dibuat)")
        else:
            # ========== STATUS TIDAK BERUBAH! ==========
            # TIDAK buat log, TIDAK kirim notifikasi
            print(f"[MANUAL CHECK] ⏭️ {service.name}: status tetap {status} (tidak buat log, hanya update last_checked)")
        
        # ========== SELALU simpan ==========
        service.save()
        print(f"[MANUAL CHECK] Service {service.name} BERHASIL DISIMPAN")
        
        # Refresh dari database untuk memastikan
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
        
        # LOG ERROR (bukan perubahan status, tapi error sistem)
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


# ======================
# MONITORING SERVICE (CHECK ALL SERVICES) - UNTUK OTOMATIS - DIPERBAIKI
# ======================
def check_all_services():
    """
    Memeriksa SEMUA service (otomatis setiap 5 menit)
    - HANYA buat log jika status berubah
    - last_checked SELALU update
    - Notifikasi HANYA jika status berubah
    """
    
    # ========== CEK INTERNET DULU! ==========
    if not is_internet_available():
        print(f"[{timezone.now()}] ⚠️ TIDAK ADA KONEKSI INTERNET! Melewati pengecekan service.")
        return  # JANGAN UPDATE APAPUN!
    
    services = Service.objects.all()
    print(f"\n[{timezone.now()}] [AUTO CHECK] ========================================")
    print(f"[AUTO CHECK] Internet OK, mulai pengecekan {services.count()} service...")
    
    for service in services:
        try:
            print(f"\n[AUTO CHECK] Mengecek service: {service.name}")
            print(f"[AUTO CHECK] last_checked SEBELUM: {service.last_checked}")
            
            status, response_time, status_code, down_reason, down_detail = check_service_status(service)
            
            # Update last_checked (SELALU update)
            service.last_checked = timezone.now()
            service.last_response_time = response_time
            service.last_status_code = status_code
            
            print(f"[AUTO CHECK] last_checked SESUDAH di-set: {service.last_checked}")
            
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
                
                # Update uptime percentage
                update_uptime_percentage(service)
                
                # Kirim notifikasi jika WARNING atau DOWN
                if status in ['WARNING', 'DOWN']:
                    send_alert(service, status, status_code, response_time, down_reason, down_detail)
                elif status == 'UP' and old_status in ['WARNING', 'DOWN']:
                    # Kirim notifikasi recovery
                    send_alert(service, status, status_code, response_time, down_reason, down_detail)
                
                print(f"[AUTO CHECK] ✅ {service.name}: {old_status} → {status} (log dibuat)")
            else:
                # ========== STATUS TIDAK BERUBAH! ==========
                # TIDAK buat log, TIDAK kirim notifikasi
                print(f"[AUTO CHECK] ⏭️ {service.name}: status tetap {status} (tidak buat log, hanya update last_checked)")
            
            # Update uptime percentage (tetap dihitung meski status tidak berubah)
            update_uptime_percentage(service)
            
            # SELALU simpan
            service.save()
            print(f"[AUTO CHECK] Service {service.name} BERHASIL DISIMPAN")
            print(f"[AUTO CHECK] ----------------------------------------")
            
        except Exception as e:
            print(f"❌ ERROR checking service {service.name}: {e}")
            import traceback
            traceback.print_exc()
            
            # LOG ERROR (bukan perubahan status, tapi error sistem)
            try:
                Log.objects.create(
                    service=service,
                    status='UNKNOWN',
                    message=f"Monitoring error: {str(e)[:200]}"
                )
            except:
                pass
    
    print(f"[{timezone.now()}] [AUTO CHECK] Selesai pengecekan semua service")
    print(f"[AUTO CHECK] ========================================\n")


# ======================
# MONITORING THREAD (UNTUK BACKGROUND TASK)
# ======================
monitoring_thread_running = False

def start_monitoring_thread():
    """Jalankan monitoring di background thread setiap 5 menit"""
    global monitoring_thread_running
    
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
    
    thread = threading.Thread(target=monitor_loop, daemon=True)
    thread.start()
    print("Monitoring thread started - akan mengecek semua service setiap 5 menit")


# ======================
# DASHBOARD (WEB)
# ======================
class DashboardView(TemplateView):
    template_name = 'services/dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        print(f"DashboardView - User: {request.user}")
        print(f"DashboardView - Is Authenticated: {request.user.is_authenticated}")
        print(f"DashboardView - Session Key: {request.session.session_key}")
        
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_dashboard_data())
        return context


# ======================
# SERVICES (WEB)
# ======================
class ServiceListView(ListView):
    model = Service
    template_name = 'services/service_list.html'
    context_object_name = 'services'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)


class ServiceCreateView(CreateView):
    model = Service
    template_name = 'services/service_form.html'
    fields = ['name', 'url', 'service_type']
    success_url = reverse_lazy('service_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Setelah service ditambahkan, langsung cek statusnya"""
        response = super().form_valid(form)
        
        # Auto check service yang baru ditambahkan
        service = self.object
        print(f"Service baru ditambahkan: {service.name} - melakukan pengecekan otomatis...")
        
        # Jalankan pengecekan otomatis
        check_single_service(service)
        
        return response


class ServiceUpdateView(UpdateView):
    model = Service
    template_name = 'services/service_form.html'
    fields = ['name', 'url', 'service_type']
    success_url = reverse_lazy('service_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Setelah service diedit, langsung cek statusnya"""
        response = super().form_valid(form)
        
        # Auto check service yang baru diedit
        service = self.object
        print(f"Service diedit: {service.name} - melakukan pengecekan otomatis...")
        
        # Jalankan pengecekan otomatis
        check_single_service(service)
        
        return response


class ServiceDeleteView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        service = get_object_or_404(Service, pk=pk)
        service.delete()
        return JsonResponse({"message": "Service dihapus"})


# ======================
# SERVICE API (DENGAN DETAIL LENGKAP)
# ======================
class ServiceAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        services = Service.objects.all()
        data = [
            {
                "id": s.id,
                "name": s.name,
                "url": s.url,
                "service_type": s.service_type,
                "status": s.last_status,
                "status_code": s.last_status_code,
                "response_time": s.last_response_time,
                "down_reason": s.last_down_reason,
                "down_detail": s.last_down_detail,
                "uptime_percentage": s.uptime_percentage,
                "last_checked": s.last_checked.strftime("%Y-%m-%d %H:%M:%S") if s.last_checked else None
            } for s in services
        ]
        return JsonResponse(data, safe=False)

    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        try:
            data = json.loads(request.body)
            service = Service.objects.create(
                name=data.get("name"),
                url=data.get("url"),
                service_type=data.get("service_type")
            )
            
            # Auto check service yang baru ditambahkan via API
            print(f"[API] Service baru ditambahkan: {service.name} - melakukan pengecekan otomatis...")
            check_single_service(service)
            
            return JsonResponse({
                "message": "Service berhasil ditambahkan dan telah dicek otomatis",
                "id": service.id,
                "status": service.last_status
            }, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


# ======================
# SERVICE DETAIL API
# ======================
class ServiceDetailAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, pk): 
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        service = get_object_or_404(Service, pk=pk)
        return JsonResponse({
            "id": service.id,
            "name": service.name,
            "url": service.url,
            "service_type": service.service_type,
            "status": service.last_status,
            "status_code": service.last_status_code,
            "response_time": service.last_response_time,
            "down_reason": service.last_down_reason,
            "down_detail": service.last_down_detail,
            "uptime_percentage": service.uptime_percentage,
            "last_checked": service.last_checked.strftime("%Y-%m-%d %H:%M:%S") if service.last_checked else None
        })

    def put(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        try:
            data = json.loads(request.body)
            service = get_object_or_404(Service, pk=pk)
            
            service.name = data.get("name")
            service.url = data.get("url")
            service.service_type = data.get("service_type")
            service.save()
            
            # Auto check service yang baru diedit via API
            print(f"[API] Service diedit: {service.name} - melakukan pengecekan otomatis...")
            check_single_service(service)
            
            return JsonResponse({
                "message": "Service diupdate dan telah dicek otomatis",
                "status": service.last_status
            })
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    def delete(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        service = get_object_or_404(Service, pk=pk)
        service.delete()
        return JsonResponse({"message": "Service dihapus"})


# ======================
# CONTACT (WEB)
# ======================
class ContactListView(ListView):
    model = Contact
    template_name = 'services/contact_list.html'
    context_object_name = 'contacts'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)


class ContactCreateView(CreateView):
    model = Contact
    template_name = 'services/contact_form.html'
    fields = ['name', 'phone_number', 'email', 'notification_channel']
    success_url = reverse_lazy('contact_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)


class ContactUpdateView(UpdateView):
    model = Contact
    template_name = 'services/contact_form.html'
    fields = ['name', 'phone_number', 'email', 'notification_channel', 'is_active']
    success_url = reverse_lazy('contact_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)


class ContactDeleteView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        contact = get_object_or_404(Contact, pk=pk)
        contact.delete()
        return JsonResponse({"message": "Contact dihapus"})


# ======================
# CONTACT API
# ======================
class ContactAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        contacts = Contact.objects.all()
        data = [
            {
                "id": c.id,
                "name": c.name,
                "phone": c.phone_number,
                "email": c.email,
                "notification_channel": c.notification_channel,
                "is_active": c.is_active
            } for c in contacts
        ]
        return JsonResponse(data, safe=False)

    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        try:
            data = json.loads(request.body)
            contact = Contact.objects.create(
                name=data.get("name"),
                phone_number=data.get("phone"),
                email=data.get("email"),
                notification_channel=data.get("notification_channel", "WHATSAPP")
            )
            return JsonResponse({
                "message": "Contact berhasil ditambahkan",
                "id": contact.id
            }, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


class ContactDetailAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def put(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        try:
            data = json.loads(request.body)
            contact = get_object_or_404(Contact, pk=pk)
            contact.name = data.get("name")
            contact.phone_number = data.get("phone")
            contact.email = data.get("email")
            contact.notification_channel = data.get("notification_channel")
            contact.is_active = data.get("is_active", True)
            contact.save()
            return JsonResponse({"message": "Contact diupdate"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    def delete(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        contact = get_object_or_404(Contact, pk=pk)
        contact.delete()
        return JsonResponse({"message": "Contact dihapus"})


# ======================
# MONITORING LOGS API (UNTUK HISTORY SEMUA SERVICE)
# ======================
class MonitoringLogsAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        try:
            service_id = request.GET.get('service_id')
            status_filter = request.GET.get('status')
            limit = int(request.GET.get('limit', 500))
            
            logs = Log.objects.all().order_by('-timestamp')[:limit]
            
            if service_id:
                logs = logs.filter(service_id=service_id)
            
            if status_filter and status_filter.lower() != 'all':
                logs = logs.filter(status__iexact=status_filter)
            
            logs_data = []
            for log in logs:
                logs_data.append({
                    'id': log.id,
                    'service_id': log.service.id if log.service else None,
                    'service_name': log.service.name if log.service else 'System',
                    'status': log.status,
                    'message': log.message or f"Service {log.status}",
                    'timestamp': log.timestamp.isoformat(),
                    'response_time': log.response_time,
                    'status_code': log.status_code,
                    'down_reason': log.down_reason,
                })
            
            return JsonResponse({
                'success': True,
                'logs': logs_data,
                'total': len(logs_data)
            }, status=200)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class MonitoringLogDetailAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        try:
            log = Log.objects.get(pk=pk)
            
            data = {
                'id': log.id,
                'service_id': log.service.id if log.service else None,
                'service_name': log.service.name if log.service else 'System',
                'status': log.status,
                'message': log.message,
                'timestamp': log.timestamp.isoformat(),
                'response_time': log.response_time,
                'status_code': log.status_code,
                'down_reason': log.down_reason,
                'created_at': log.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(log, 'created_at') else log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return JsonResponse({
                'success': True,
                'log': data
            }, status=200)
            
        except Log.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Log tidak ditemukan'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


# ======================
# SERVICE LOG API (UNTUK HISTORY PER SERVICE)
# ======================
class ServiceLogAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        service = get_object_or_404(Service, pk=pk)
        logs = service.log_set.all().order_by('-timestamp')[:50]
        
        data = [
            {
                "status": log.status,
                "status_code": log.status_code,
                "response_time": log.response_time,
                "down_reason": log.down_reason,
                "message": log.message,
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            } for log in logs
        ]
        return JsonResponse(data, safe=False)


# ======================
# POWER (WEB)
# ======================
class PowerView(TemplateView):
    template_name = 'services/power.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)


# ======================
# POWER API (WEB DASHBOARD)
# ======================
@method_decorator(csrf_exempt, name='dispatch')
class PowerDataAPI(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        device_id = request.GET.get('device_id')
        
        if device_id:
            logs = PowerLog.objects.filter(device_id=device_id).order_by('-timestamp')[:10]
        else:
            logs = PowerLog.objects.all().order_by('-timestamp')[:10]

        logs_list = list(reversed(logs))
        
        labels = []
        voltages = []
        currents = []
        powers = []
        
        for log in logs_list:
            labels.append(log.timestamp.strftime("%H:%M:%S"))
            voltages.append(log.voltage)
            currents.append(log.current)
            powers.append(log.power)
        
        return JsonResponse({
            "labels": labels,
            "voltage": voltages,
            "current": currents,
            "power": powers,
        })


# ======================
# IoT API (UNTUK ESP32/DEVICE IOT) - DIPERBAIKI DENGAN API KEY CONSISTENT
# ======================
@method_decorator(csrf_exempt, name='dispatch')
class PowerCreateAPI(View):
    """
    API untuk menerima data dari IoT devices (ESP32, Arduino, dll)
    Menggunakan API Key authentication
    """
    
    def verify_api_key(self, request):
        """Verifikasi API Key dari header"""
        api_key = request.headers.get('X-API-KEY')
        
        # Cek apakah API Key ada dan match dengan settings
        if not api_key:
            return False, "API Key tidak ditemukan di header 'X-API-KEY'"
        
        if api_key != getattr(settings, 'API_KEY', None):
            return False, "API Key tidak valid"
        
        return True, "Valid"
    
    def post(self, request):
        # Verifikasi API Key
        is_valid, message = self.verify_api_key(request)
        if not is_valid:
            return JsonResponse({'error': message}, status=403)

        try:
            # Parse JSON data
            data = json.loads(request.body)
            device_id = data.get('device_id')
            voltage = data.get('voltage')
            current = data.get('current')
            power = data.get('power')
            
            # Validasi required fields
            if voltage is None or current is None or power is None:
                return JsonResponse({
                    'error': 'Missing required fields: voltage, current, power are required'
                }, status=400)
            
            # Cari atau gunakan device
            if device_id:
                try:
                    device = Device.objects.get(id=device_id)
                except Device.DoesNotExist:
                    return JsonResponse({
                        'error': f'Device with id {device_id} not found. Please create device first.'
                    }, status=400)
            else:
                # Jika tidak ada device_id, gunakan device pertama atau buat default
                device = Device.objects.first()
                if not device:
                    # Auto-create default device (opsional)
                    device = Device.objects.create(
                        id=1,
                        name='Default-IoT-Device',
                        location='Unknown',
                        status='ONLINE'
                    )
                    print(f"[IoT API] Auto-created default device with ID: {device.id}")
            
            # Update device status dan last_seen
            device.last_seen = timezone.now()
            
            # Cek apakah device sebelumnya offline
            was_offline = (device.status == 'OFFLINE')
            if was_offline:
                device.status = 'ONLINE'
                device.save()
                # Kirim notifikasi device online kembali
                try:
                    from .utils import send_device_alert
                    send_device_alert(device, is_offline=False)
                except Exception as e:
                    print(f"Error sending device alert: {e}")
            else:
                device.save(update_fields=['last_seen'])
            
            # Simpan data power
            power_log = PowerLog.objects.create(
                device=device,
                voltage=voltage,
                current=current,
                power=power
            )
            
            # Cek threshold untuk alert (opsional)
            alert_sent = False
            if device.threshold_voltage and voltage < device.threshold_voltage:
                try:
                    from .utils import send_power_alert
                    send_power_alert(device, f"Voltage rendah: {voltage}V < {device.threshold_voltage}V", 
                                   voltage, current, power)
                    alert_sent = True
                except:
                    pass
            
            if device.threshold_current and current > device.threshold_current:
                try:
                    from .utils import send_power_alert
                    send_power_alert(device, f"Current tinggi: {current}A > {device.threshold_current}A",
                                   voltage, current, power)
                    alert_sent = True
                except:
                    pass
            
            # Return success response
            response_data = {
                "success": True,
                "message": "Data power berhasil disimpan",
                "id": power_log.id,
                "device_id": device.id,
                "device_name": device.name,
                "device_status": device.status,
                "voltage": power_log.voltage,
                "current": power_log.current,
                "power": power_log.power,
                "timestamp": power_log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            if alert_sent:
                response_data["alert"] = "Threshold alert telah dikirim"
            
            return JsonResponse(response_data, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        except KeyError as e:
            return JsonResponse({"error": f"Missing field: {str(e)}"}, status=400)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)


# ======================
# TRIGGER MONITORING API
# ======================
@method_decorator(csrf_exempt, name='dispatch')
class StartMonitoringAPI(View):
    def get(self, request):
        """Cek status monitoring thread"""
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        return JsonResponse({
            "monitoring_active": monitoring_thread_running,
            "message": "Monitoring thread is running" if monitoring_thread_running else "Monitoring thread is not running"
        })
    
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        start_monitoring_thread()
        return JsonResponse({"message": "Monitoring thread started", "active": True})


# ======================
# AUTH API
# ======================
class LoginAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        try:
            data = json.loads(request.body)
            username = data.get("username")
            password = data.get("password")
        except:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        if not username or not password:
            return JsonResponse({"error": "Username & password wajib"}, status=400)

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            request.session.save()
            print(f"Login berhasil: {username}")
            print(f"Session key: {request.session.session_key}")
            
            return JsonResponse({
                "success": True,
                "message": "Login berhasil",
                "username": user.username
            })

        print(f"Login gagal: {username}")
        return JsonResponse({"success": False, "error": "Username atau password salah"}, status=401)


class RegisterAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        try:
            data = json.loads(request.body)
            username = data.get("username")
            password = data.get("password")
        except:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        if not username or not password:
            return JsonResponse({"error": "Username & password wajib"}, status=400)

        if User.objects.filter(username=username).exists():
            return JsonResponse({"error": "Username sudah ada"}, status=400)

        user = User.objects.create_user(
            username=username,
            password=password
        )

        return JsonResponse({
            "message": "User berhasil dibuat",
            "username": user.username
        })


class LogoutAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        if request.user.is_authenticated:
            logout(request)
        return JsonResponse({"message": "Logout berhasil"})


# ======================
# LOGIN PAGE
# ======================
class LoginPageView(TemplateView):
    template_name = 'services/login.html'


# ======================
# DASHBOARD API
# ======================
@method_decorator(csrf_exempt, name='dispatch')
class DashboardAPI(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        data = get_dashboard_data()
        return JsonResponse(data)


# ======================
# CHECK AUTH API
# ======================
class CheckAuthAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        return JsonResponse({
            "is_authenticated": request.user.is_authenticated,
            "username": request.user.username if request.user.is_authenticated else None
        })


@method_decorator(csrf_exempt, name='dispatch')
class DebugSessionAPI(View):
    def get(self, request):
        return JsonResponse({
            "is_authenticated": request.user.is_authenticated,
            "username": request.user.username if request.user.is_authenticated else None,
            "session_key": request.session.session_key,
            "session_items": dict(request.session.items()),
            "cookies": request.COOKIES.get('sessionid', None)
        })


# ======================
# MANUAL CHECK API
# ======================
@method_decorator(csrf_exempt, name='dispatch')
class ManualCheckAPI(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        service = get_object_or_404(Service, pk=pk)
        
        try:
            result = check_single_service(service)
            
            if result['success']:
                return JsonResponse({
                    "success": True,
                    "status": result['status'],
                    "status_code": result['status_code'],
                    "response_time": result['response_time']
                })
            else:
                return JsonResponse({"error": result.get('error', 'Check failed')}, status=400)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=400)


# ======================
# DEVICE API
# ======================
class DeviceAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        devices = Device.objects.all()
        data = [
            {
                "id": d.id,
                "name": d.name,
                "location": d.location,
                "status": d.status,
                "last_seen": d.last_seen.strftime("%Y-%m-%d %H:%M:%S") if d.last_seen else None,
                "has_power_backup": d.has_power_backup,
                "wifi_ssid": d.wifi_ssid,
                "wifi_config_count": d.wifi_config_count,
                "threshold_voltage": d.threshold_voltage,
                "threshold_current": d.threshold_current,
            } for d in devices
        ]
        return JsonResponse(data, safe=False)


# ======================
# MONITORING STATUS API (BARU) - UNTUK CEK STATUS THREAD
# ======================
@method_decorator(csrf_exempt, name='dispatch')
class MonitoringStatusAPI(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        total_services = Service.objects.count()
        last_log = Log.objects.first()
        
        return JsonResponse({
            "monitoring_thread_active": monitoring_thread_running,
            "total_services": total_services,
            "last_check_time": timezone.now().isoformat(),
            "last_log_time": last_log.timestamp.isoformat() if last_log else None
        })