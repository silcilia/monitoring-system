from django.views.generic import ListView, CreateView, TemplateView, UpdateView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict

from .models import Service, Contact, PowerLog, Log

# ======================
# AUTH & DJANGO
# ======================
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout

# ======================
# DRF
# ======================
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from rest_framework_simplejwt.tokens import RefreshToken


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
        if not request.user.is_authenticated:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_dashboard_data())
        return context


# ======================
# 🔥 DASHBOARD API
# ======================
class DashboardAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_dashboard_data())


# ======================
# SERVICES (WEB)
# ======================
class ServiceListView(ListView):
    model = Service
    template_name = 'services/service_list.html'
    context_object_name = 'services'


class ServiceCreateView(CreateView):
    model = Service
    template_name = 'services/service_form.html'
    fields = ['name', 'url', 'service_type']
    success_url = reverse_lazy('service_list')


class ServiceUpdateView(UpdateView):
    model = Service
    template_name = 'services/service_form.html'
    fields = ['name', 'url', 'service_type']
    success_url = reverse_lazy('service_list')


class ServiceDeleteView(View):
    def post(self, request, pk):
        service = get_object_or_404(Service, pk=pk)
        service.delete()
        return redirect('service_list')


# ======================
# SERVICE API
# ======================
class ServiceAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
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

        return Response(data)

    def post(self, request):
        service = Service.objects.create(
            name=request.data.get("name"),
            url=request.data.get("url"),
            service_type=request.data.get("service_type")
        )

        return Response({
            "message": "Service berhasil ditambahkan",
            "id": service.id
        }, status=201)


class ServiceDetailAPI(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        service = get_object_or_404(Service, pk=pk)

        service.name = request.data.get("name")
        service.url = request.data.get("url")
        service.service_type = request.data.get("service_type")
        service.save()

        return Response({"message": "Service diupdate"})

    def delete(self, request, pk):
        service = get_object_or_404(Service, pk=pk)
        service.delete()

        return Response({"message": "Service dihapus"})

# ======================
# CONTACT (WEB)
# ======================
class ContactListView(ListView):
    model = Contact
    template_name = 'services/contact_list.html'
    context_object_name = 'contacts'


class ContactCreateView(CreateView):
    model = Contact
    template_name = 'services/contact_form.html'
    fields = ['name', 'phone_number']
    success_url = reverse_lazy('contact_list')


class ContactUpdateView(UpdateView):
    model = Contact
    template_name = 'services/contact_form.html'
    fields = ['name', 'phone_number']
    success_url = reverse_lazy('contact_list')


class ContactDeleteView(View):
    def post(self, request, pk):
        contact = get_object_or_404(Contact, pk=pk)
        contact.delete()
        return redirect('contact_list')

# ======================
# CONTACT API
# ======================
class ContactAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        contacts = Contact.objects.all()
        data = [
            {
                "id": c.id,
                "name": c.name,
                "phone": c.phone_number
            } for c in contacts
        ]
        return Response(data)

    def post(self, request):
        contact = Contact.objects.create(
            name=request.data.get("name"),
            phone_number=request.data.get("phone_number")
        )

        return Response({"message": "Contact dibuat", "id": contact.id})


class ContactDetailAPI(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        contact = get_object_or_404(Contact, pk=pk)
        contact.name = request.data.get("name")
        contact.phone_number = request.data.get("phone_number")
        contact.save()

        return Response({"message": "Contact diupdate"})

    def delete(self, request, pk):
        contact = get_object_or_404(Contact, pk=pk)
        contact.delete()

        return Response({"message": "Contact dihapus"})


# ======================
# POWER (WEB)
# ======================
class PowerView(TemplateView):
    template_name = 'services/power.html'


# ======================
# 🔥 POWER API
# ======================
class PowerDataAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logs = PowerLog.objects.order_by('-timestamp')[:10]

        return Response({
            "labels": [log.timestamp.strftime("%H:%M:%S") for log in logs][::-1],
            "voltage": [log.voltage for log in logs][::-1],
            "current": [log.current for log in logs][::-1],
            "power": [log.power for log in logs][::-1],
        })


class PowerCreateAPI(APIView):
    def post(self, request):
        PowerLog.objects.create(
            voltage=request.data.get("voltage"),
            current=request.data.get("current"),
            power=request.data.get("power")
        )

        return Response({"message": "Data power masuk"})


# ======================
# AUTH API
# ======================
class LoginAPI(APIView):
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "Username dan password wajib diisi"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(username=username, password=password)

        if user:
            login(request, user)  # session login

            refresh = RefreshToken.for_user(user)

            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "username": user.username
            })

        return Response(
            {"error": "Username atau password salah"},
            status=status.HTTP_401_UNAUTHORIZED
        )


class RegisterAPI(APIView):
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username sudah ada"}, status=400)

        user = User.objects.create_user(username=username, password=password)

        return Response({
            "message": "User berhasil dibuat",
            "username": user.username
        })


class LogoutAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)

        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except:
            pass

        return Response({"message": "Logout berhasil"})


# ======================
# LOGIN PAGE
# ======================
class LoginPageView(TemplateView):
    template_name = 'services/login.html'