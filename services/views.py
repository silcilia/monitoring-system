from django.views.generic import ListView, CreateView, TemplateView, UpdateView
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict
from django.http import JsonResponse
from django.conf import settings
import threading
import time
import json
import logging

# ================================================================
# IMPORT UTILS (FUNGSI DASAR) - HANYA DARI utils.py
# ================================================================
from .utils import (
    check_service_status,
    update_uptime_percentage,
    is_internet_available,
    send_notification,
    WEIGHT_UP,
    WEIGHT_WARNING,
    WEIGHT_DOWN,
)

# ================================================================
# IMPORT MONITORING (FUNGSI MONITORING) - DARI monitoring.py
# ================================================================
from .monitoring import (
    send_alert,
    send_device_alert,
    check_device_statuses,
    check_single_service as monitoring_check_single_service,
    check_all_services as monitoring_check_all_services,
    start_monitoring_thread as monitoring_start_thread,
    monitoring_thread_running,
)

# ================================================================
# IMPORT MODELS
# ================================================================
from .models import (
    Service, Contact, PowerLog, Log, Device, 
    ServiceContact, DeviceContact, NotificationLog
)

# ================================================================
# IMPORT DJANGO AUTH
# ================================================================
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout

# ================================================================
# IMPORT CSRF & DECORATORS
# ================================================================
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)


# ================================================================
# SECTION 1: HELPER FUNCTIONS
# ================================================================

def get_dashboard_data():
    """
    Mengambil data untuk ditampilkan di dashboard
    ================================================================
    Sekarang menggunakan bobot yang SAMA dengan perhitungan uptime:
    - UP = 100%
    - WARNING = 70%
    - DOWN = 0%
    
    Returns:
        dict: Berisi total, up, warning, down, percent, labels, data
    """
    services = Service.objects.all()

    total = services.count()
    up = services.filter(last_status='UP').count()
    warning = services.filter(last_status='WARNING').count()
    down = services.filter(last_status='DOWN').count()

    percent = int((up / total) * 100) if total > 0 else 0

    # ========== CHART 7 HARI TERAKHIR DENGAN BOBOT ==========
    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=6)
    
    # Ambil semua log 7 hari terakhir (abaikan NO_INTERNET)
    logs = Log.objects.filter(
        timestamp__date__gte=seven_days_ago
    ).exclude(
        down_reason='NO_INTERNET'
    )

    # Kelompokkan log berdasarkan hari
    daily_logs = defaultdict(list)
    for log in logs:
        day = log.timestamp.date()
        daily_logs[day].append(log)

    labels = []
    data = []

    for i in range(7):
        day = seven_days_ago + timedelta(days=i)
        day_logs = daily_logs.get(day, [])
        
        if day_logs:
            # Hitung total bobot untuk hari ini (SAMA dengan rumus uptime)
            total_weight = 0
            for log in day_logs:
                if log.status == 'UP':
                    total_weight += WEIGHT_UP      # 100
                elif log.status == 'WARNING':
                    total_weight += WEIGHT_WARNING # 70
                elif log.status == 'DOWN':
                    total_weight += WEIGHT_DOWN    # 0
            
            # Rata-rata bobot = persentase hari itu
            percent_day = int((total_weight / len(day_logs)))
        else:
            # Tidak ada log, anggap 100% (semua service UP)
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


# ================================================================
# SECTION 2: FUNGSI CHECK SINGLE SERVICE (WRAPPER)
# ================================================================

def check_single_service(service):
    """
    WRAPPER untuk memanggil fungsi dari monitoring.py
    ================================================================
    """
    return monitoring_check_single_service(service)


def check_all_services():
    """
    WRAPPER untuk memanggil fungsi dari monitoring.py
    ================================================================
    """
    return monitoring_check_all_services()


def start_monitoring_thread():
    """
    WRAPPER untuk memanggil fungsi dari monitoring.py
    ================================================================
    """
    return monitoring_start_thread()


# ================================================================
# SECTION 3: DASHBOARD VIEW (WEB)
# ================================================================

class DashboardView(TemplateView):
    """
    Halaman utama dashboard monitoring
    ================================================================
    Menampilkan ringkasan status service dan chart uptime
    """
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


# ================================================================
# SECTION 4: SERVICE MANAGEMENT (WEB)
# ================================================================

class ServiceListView(ListView):
    """Halaman daftar service"""
    model = Service
    template_name = 'services/service_list.html'
    context_object_name = 'services'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)


class ServiceCreateView(CreateView):
    """Halaman tambah service baru"""
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
        service = self.object
        print(f"Service baru ditambahkan: {service.name} - melakukan pengecekan otomatis...")
        check_single_service(service)
        return response


class ServiceUpdateView(UpdateView):
    """Halaman edit service"""
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
        service = self.object
        print(f"Service diedit: {service.name} - melakukan pengecekan otomatis...")
        check_single_service(service)
        return response


class ServiceDeleteView(View):
    """Hapus service (via AJAX)"""
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        service = get_object_or_404(Service, pk=pk)
        service.delete()
        return JsonResponse({"message": "Service dihapus"})


# ================================================================
# SECTION 5: CONTACT MANAGEMENT (WEB)
# ================================================================

class ContactListView(ListView):
    """Halaman daftar kontak"""
    model = Contact
    template_name = 'services/contact_list.html'
    context_object_name = 'contacts'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)


class ContactCreateView(CreateView):
    """Halaman tambah kontak baru"""
    model = Contact
    template_name = 'services/contact_form.html'
    fields = ['name', 'phone_number', 'email', 'notification_channel']
    success_url = reverse_lazy('contact_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)


class ContactUpdateView(UpdateView):
    """Halaman edit kontak"""
    model = Contact
    template_name = 'services/contact_form.html'
    fields = ['name', 'phone_number', 'email', 'notification_channel', 'is_active']
    success_url = reverse_lazy('contact_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)


class ContactDeleteView(View):
    """Hapus kontak (via AJAX)"""
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        contact = get_object_or_404(Contact, pk=pk)
        contact.delete()
        return JsonResponse({"message": "Contact dihapus"})


# ================================================================
# SECTION 6: POWER / IoT MONITORING (WEB)
# ================================================================

class PowerView(TemplateView):
    """Halaman monitoring power (ESP32)"""
    template_name = 'services/power.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)


# ================================================================
# SECTION 7: API ENDPOINTS (CSRF_EXEMPT)
# ================================================================

# ----- AUTH API -----
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
            return JsonResponse({
                "success": True,
                "message": "Login berhasil",
                "username": user.username
            })

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

        user = User.objects.create_user(username=username, password=password)
        return JsonResponse({"message": "User berhasil dibuat", "username": user.username})


class LogoutAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        if request.user.is_authenticated:
            logout(request)
        return JsonResponse({"message": "Logout berhasil"})


class CheckAuthAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        return JsonResponse({
            "is_authenticated": request.user.is_authenticated,
            "username": request.user.username if request.user.is_authenticated else None
        })


# ----- DASHBOARD API -----
class DashboardAPI(View):
    @method_decorator(csrf_exempt, name='dispatch')
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        data = get_dashboard_data()
        return JsonResponse(data)


# ----- SERVICE API -----
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
            print(f"[API] Service baru ditambahkan: {service.name} - melakukan pengecekan otomatis...")
            check_single_service(service)
            return JsonResponse({
                "message": "Service berhasil ditambahkan dan telah dicek otomatis",
                "id": service.id,
                "status": service.last_status
            }, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


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


class ManualCheckAPI(View):
    @method_decorator(csrf_exempt, name='dispatch')
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
            return JsonResponse({"error": str(e)}, status=400)


# ----- CONTACT API -----
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


# ----- MONITORING LOGS API -----
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
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


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
            }
            return JsonResponse({'success': True, 'log': data}, status=200)
        except Log.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Log tidak ditemukan'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


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


# ----- POWER / IoT API -----
class PowerDataAPI(View):
    @method_decorator(csrf_exempt, name='dispatch')
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


class PowerCreateAPI(View):
    """
    API untuk menerima data dari IoT devices (ESP32, Arduino, dll)
    ================================================================
    Menggunakan API Key authentication (header X-API-KEY)
    """
    
    @method_decorator(csrf_exempt, name='dispatch')
    def post(self, request):
        # VERIFIKASI API KEY
        api_key = request.headers.get('X-API-KEY')
        expected_api_key = getattr(settings, 'API_KEY', None)
        
        if not api_key:
            return JsonResponse({'error': 'API Key tidak ditemukan di header X-API-KEY'}, status=401)
        
        if expected_api_key and api_key != expected_api_key:
            return JsonResponse({'error': 'API Key tidak valid'}, status=403)

        try:
            data = json.loads(request.body)
            device_id = data.get('device_id')
            voltage = data.get('voltage')
            current = data.get('current')
            power = data.get('power')
            
            # VALIDASI REQUIRED FIELDS
            if voltage is None or current is None or power is None:
                return JsonResponse({
                    'error': 'Missing required fields: voltage, current, power are required'
                }, status=400)
            
            # CARI ATAU BUAT DEVICE
            if device_id:
                try:
                    device = Device.objects.get(id=device_id)
                except Device.DoesNotExist:
                    return JsonResponse({
                        'error': f'Device with id {device_id} not found'
                    }, status=404)
            else:
                device = Device.objects.first()
                if not device:
                    device = Device.objects.create(
                        name='Default-IoT-Device',
                        location='Unknown',
                        status='ONLINE'
                    )
                    print(f"[IoT API] Auto-created default device with ID: {device.id}")
            
            # UPDATE DEVICE STATUS
            device.last_seen = timezone.now()
            was_offline = (device.status == 'OFFLINE')
            
            if was_offline:
                device.status = 'ONLINE'
                device.save()
                try:
                    send_device_alert(device, is_offline=False)
                except Exception as e:
                    print(f"Error sending device alert: {e}")
            else:
                device.save(update_fields=['last_seen'])
            
            # SIMPAN DATA POWER
            power_log = PowerLog.objects.create(
                device=device,
                voltage=voltage,
                current=current,
                power=power
            )
            
            # CEK THRESHOLD (LISTRIK BERMASALAH)
            alert_messages = []
            if device.threshold_voltage and voltage < device.threshold_voltage:
                alert_messages.append(f"Voltage : {voltage}V (Normal: >{device.threshold_voltage}V)")
            
            if device.threshold_current and current > device.threshold_current:
                alert_messages.append(f"Arus : {current}A (Normal: <{device.threshold_current}A)")
            
            if alert_messages:
                try:
                    send_device_alert(device, is_offline=False, extra_messages=alert_messages)
                    print(f"[IoT API] Power alert untuk {device.name}: {alert_messages}")
                except Exception as e:
                    print(f"Error sending power alert: {e}")
            
            # RETURN SUCCESS RESPONSE
            return JsonResponse({
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
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)


class StartMonitoringAPI(View):
    @method_decorator(csrf_exempt, name='dispatch')
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


class MonitoringStatusAPI(View):
    @method_decorator(csrf_exempt, name='dispatch')
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


# ================================================================
# SECTION 8: UTILITY API (DEBUG)
# ================================================================

class LoginPageView(TemplateView):
    """Halaman login"""
    template_name = 'services/login.html'


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