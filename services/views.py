from django.views.generic import ListView, CreateView, TemplateView, UpdateView
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict
from django.http import JsonResponse

from .models import Service, Contact, PowerLog, Log

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
# HELPER DASHBOARD
# ======================
def get_dashboard_data():
    services = Service.objects.all()

    total = services.count()
    up = services.filter(last_status='UP').count()
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
        'down': down,
        'percent': percent,
        'labels': labels,
        'data': data,
    }


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
# SERVICE API
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
                "status": s.last_status
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


class ServiceDetailAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

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
    fields = ['name', 'phone_number']
    success_url = reverse_lazy('contact_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)


class ContactUpdateView(UpdateView):
    model = Contact
    template_name = 'services/contact_form.html'
    fields = ['name', 'phone_number']
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
                "phone": c.phone_number
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
                phone_number=data.get("phone")
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
class PowerDataAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        logs = PowerLog.objects.order_by('-timestamp')[:10]
        
        data = {
            "labels": [log.timestamp.strftime("%H:%M:%S") for log in logs][::-1],
            "voltage": [log.voltage for log in logs][::-1],
            "current": [log.current for log in logs][::-1],
            "power": [log.power for log in logs][::-1],
        }
        return JsonResponse(data)


# ======================
# IoT API (API KEY)
# ======================
class PowerCreateAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        api_key = request.headers.get('X-API-KEY')

        if api_key != 'SECRET123':
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        try:
            data = json.loads(request.body)
            PowerLog.objects.create(
                voltage=data.get("voltage"),
                current=data.get("current"),
                power=data.get("power")
            )
            return JsonResponse({"message": "Data power masuk"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


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
            # 🔥 LOGIN USER
            login(request, user)
            
            # 🔥 FORCE SAVE SESSION
            request.session.save()
            
            # 🔥 PRINT UNTUK DEBUG
            print(f"Login berhasil: {username}")
            print(f"Session key: {request.session.session_key}")
            
            return JsonResponse({
                "success": True,
                "message": "Login berhasil",
                "username": user.username
            })

        print(f"❌ Login gagal: {username}")
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
class DashboardAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        return JsonResponse(get_dashboard_data())


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

