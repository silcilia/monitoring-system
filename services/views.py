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
import time

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
from .utils import check_service_status, send_alert, update_uptime_percentage


# ======================
# HELPER DASHBOARD
# ======================
def get_dashboard_data():
    services = Service.objects.all()

    total = services.count()
    up = services.filter(last_status='UP').count()
    down = services.filter(last_status='DOWN').count()
    degraded = services.filter(last_status='DEGRADED').count()

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
        'down': down,
        'degraded': degraded,
        'percent': percent,
        'labels': labels,
        'data': data,
    }


# ======================
# MONITORING SERVICE (CHECK ALL SERVICES)
# ======================
def check_all_services():
    """Memeriksa semua service dan update status"""
    services = Service.objects.all()
    
    for service in services:
        try:
            # Gunakan fungsi dari utils.py
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
            else:
                # Status tidak berubah, tetap update log jika perlu
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
            print(f"Error checking service {service.name}: {e}")
            
            # Log error
            Log.objects.create(
                service=service,
                status='UNKNOWN',
                message=f"Monitoring error: {str(e)[:200]}"
            )


# ======================
# MONITORING THREAD (UNTUK BACKGROUND TASK)
# ======================
monitoring_thread_running = False

def start_monitoring_thread():
    """Jalankan monitoring di background thread"""
    global monitoring_thread_running
    
    if monitoring_thread_running:
        return
    
    def monitor_loop():
        global monitoring_thread_running
        monitoring_thread_running = True
        
        while monitoring_thread_running:
            try:
                print("Running scheduled monitoring check...")
                check_all_services()
            except Exception as e:
                print(f"Monitoring error: {e}")
            
            # Tunggu 5 menit sebelum cek lagi
            time.sleep(300)  # 300 detik = 5 menit
    
    thread = threading.Thread(target=monitor_loop, daemon=True)
    thread.start()
    print("Monitoring thread started")


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


class ServiceUpdateView(UpdateView):
    model = Service
    template_name = 'services/service_form.html'
    fields = ['name', 'url', 'service_type']
    success_url = reverse_lazy('service_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)


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
            return JsonResponse({
                "message": "Service berhasil ditambahkan",
                "id": service.id
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

    def get(self, request, pk):  # 🔥 TAMBAHKAN method GET
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
            return JsonResponse({"message": "Service diupdate"})
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
# SERVICE LOG API (UNTUK HISTORY)
# ======================
class ServiceLogAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, service_id):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        service = get_object_or_404(Service, pk=service_id)
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
# POWER API
# ======================
@method_decorator(csrf_exempt, name='dispatch')
class PowerDataAPI(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        # Ambil device_id dari parameter (optional)
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
# IoT API (API KEY)
# ======================
@method_decorator(csrf_exempt, name='dispatch')
class PowerCreateAPI(View):
    def post(self, request):
        api_key = request.headers.get('X-API-KEY')
        if api_key != 'jusavocad':
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        try:
            data = json.loads(request.body)
            device_id = data.get('device_id')
            
            if device_id:
                try:
                    device = Device.objects.get(id=device_id)
                    # Update last_seen
                    device.last_seen = timezone.now()
                    if device.status == 'OFFLINE':
                        device.status = 'ONLINE'
                        # Kirim notifikasi device online
                        from .utils import send_device_alert
                        send_device_alert(device, is_offline=False)
                    device.save()
                except Device.DoesNotExist:
                    return JsonResponse({'error': f'Device with id {device_id} not found'}, status=400)
            else:
                device = Device.objects.first()
                if not device:
                    return JsonResponse({'error': 'No device available. Please create a device first.'}, status=400)
            
            power_log = PowerLog.objects.create(
                device=device,
                voltage=data.get('voltage'),
                current=data.get('current'),
                power=data.get('power')
            )
            
            # Cek threshold
            if data.get('voltage', 0) < device.threshold_voltage:
                from .utils import send_device_alert
                # Kirim alert threshold jika perlu
                pass
            
            return JsonResponse({
                "message": "Data power berhasil disimpan",
                "id": power_log.id,
                "device_id": device.id,
                "device_name": device.name,
                "voltage": power_log.voltage,
                "current": power_log.current,
                "power": power_log.power,
                "timestamp": power_log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            }, status=201)
            
        except KeyError as e:
            return JsonResponse({"error": f"Missing field: {str(e)}"}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


# ======================
# MANUAL CHECK API (Untuk test dari frontend)
# ======================
@method_decorator(csrf_exempt, name='dispatch')
class ManualCheckAPI(View):
    def post(self, request, service_id):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        service = get_object_or_404(Service, pk=service_id)
        
        try:
            status, response_time, status_code, down_reason, down_detail = check_service_status(service)
            
            old_status = service.last_status
            
            service.last_checked = timezone.now()
            service.last_response_time = response_time
            service.last_status_code = status_code
            service.last_status = status
            service.last_down_reason = down_reason
            service.last_down_detail = down_detail
            service.save()
            
            # Simpan log
            Log.objects.create(
                service=service,
                status=status,
                status_code=status_code,
                response_time=response_time,
                down_reason=down_reason,
                message=down_detail
            )
            
            # Kirim notifikasi jika perlu
            if status in ['DOWN', 'DEGRADED'] and old_status != status:
                send_alert(service, status, status_code, response_time, down_reason, down_detail)
            elif status == 'UP' and old_status in ['DOWN', 'DEGRADED']:
                send_alert(service, status, status_code, response_time, down_reason, down_detail)
            
            # Update uptime
            update_uptime_percentage(service)
            
            return JsonResponse({
                "success": True,
                "status": status,
                "status_code": status_code,
                "response_time": response_time,
                "down_reason": down_reason,
                "down_detail": down_detail
            })
            
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


# ======================
# TRIGGER MONITORING API (Start monitoring thread)
# ======================
@method_decorator(csrf_exempt, name='dispatch')
class StartMonitoringAPI(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        start_monitoring_thread()
        return JsonResponse({"message": "Monitoring thread started"})


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
# DASHBOARD API (SINGLE - HAPUS DUPLICATE)
# ======================
@method_decorator(csrf_exempt, name='dispatch')
class DashboardAPI(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        data = get_dashboard_data()
        return JsonResponse(data)


# ======================
# CHECK AUTH API (Untuk Debug)
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
# MANUAL CHECK API (Untuk test dari frontend)
# ======================
@method_decorator(csrf_exempt, name='dispatch')
class ManualCheckAPI(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        service = get_object_or_404(Service, pk=pk)
        
        try:
            # Panggil fungsi check_service_status dari utils
            from .utils import check_service_status, send_alert, update_uptime_percentage
            
            status, response_time, status_code, down_reason, down_detail = check_service_status(service)
            
            old_status = service.last_status
            
            # Update service
            service.last_checked = timezone.now()
            service.last_response_time = response_time
            service.last_status_code = status_code
            service.last_status = status
            service.last_down_reason = down_reason
            service.last_down_detail = down_detail
            service.save()
            
            # Simpan log
            from .models import Log
            Log.objects.create(
                service=service,
                status=status,
                status_code=status_code,
                response_time=response_time,
                down_reason=down_reason,
                message=down_detail
            )
            
            # Kirim notifikasi jika perlu
            if status in ['DOWN', 'DEGRADED'] and old_status != status:
                send_alert(service, status, status_code, response_time, down_reason, down_detail)
            elif status == 'UP' and old_status in ['DOWN', 'DEGRADED']:
                send_alert(service, status, status_code, response_time, down_reason, down_detail)
            
            # Update uptime
            update_uptime_percentage(service)
            
            return JsonResponse({
                "success": True,
                "status": status,
                "status_code": status_code,
                "response_time": response_time,
                "down_reason": down_reason,
                "down_detail": down_detail
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=400)

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