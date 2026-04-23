from django.views.generic import ListView, CreateView, TemplateView
from django.urls import reverse_lazy
from django.http import JsonResponse
from .models import Service, Contact, PowerLog


# ======================
# DASHBOARD (FULL PAGE)
# ======================
class DashboardView(TemplateView):
    template_name = 'services/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        services = Service.objects.all()

        total = services.count()
        up = services.filter(last_status='UP').count()
        down = services.filter(last_status='DOWN').count()

        # 🔥 FIX persen (hindari error CSS)
        percent = 0
        if total > 0:
            percent = int((up / total) * 100)

        context.update({
            'services': services,
            'total': total,
            'up': up,
            'down': down,
            'percent': percent
        })

        return context


# ======================
# SERVICE
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


# ======================
# CONTACT
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


# ======================
# SPA LOAD (PARTIAL)
# ======================

class LoadDashboardView(TemplateView):
    template_name = 'services/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        services = Service.objects.all()

        total = services.count()
        up = services.filter(last_status='UP').count()
        down = services.filter(last_status='DOWN').count()

        percent = 0
        if total > 0:
            percent = int((up / total) * 100)

        context.update({
            'services': services,
            'total': total,
            'up': up,
            'down': down,
            'percent': percent
        })

        return context


class LoadServiceListView(ListView):
    model = Service
    template_name = 'services/service_list.html'
    context_object_name = 'services'


class LoadContactListView(ListView):
    model = Contact
    template_name = 'services/contact_list.html'
    context_object_name = 'contacts'


# ======================
# POWER DASHBOARD
# ======================
class PowerView(TemplateView):
    template_name = 'services/power.html'


# ======================
# API POWER DATA
# ======================
def power_data(request):
    logs = PowerLog.objects.order_by('-timestamp')[:10]

    data = {
        "labels": [log.timestamp.strftime("%H:%M:%S") for log in logs][::-1],
        "voltage": [log.voltage for log in logs][::-1],
        "current": [log.current for log in logs][::-1],
        "power": [log.power for log in logs][::-1],
    }

    return JsonResponse(data)