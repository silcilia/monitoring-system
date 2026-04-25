from django.views.generic import ListView, CreateView, TemplateView
from django.urls import reverse_lazy
from django.http import JsonResponse
from .models import Service, Contact, PowerLog


# ======================
# DASHBOARD
# ======================
class DashboardView(TemplateView):
    template_name = 'services/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        services = Service.objects.all()

        total = services.count()
        up = services.filter(last_status='UP').count()
        down = services.filter(last_status='DOWN').count()

        percent = int((up / total) * 100) if total > 0 else 0

        context.update({
            'services': services,
            'total': total,
            'up': up,
            'down': down,
            'percent': percent
        })
        return context


class LoadDashboardView(DashboardView):
    pass


# ======================
# SERVICE
# ======================
class ServiceListView(ListView):
    model = Service
    template_name = 'services/service_list.html'
    context_object_name = 'services'


class LoadServiceListView(ServiceListView):
    pass


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


class LoadContactListView(ContactListView):
    pass


class ContactCreateView(CreateView):
    model = Contact
    template_name = 'services/contact_form.html'
    fields = ['name', 'phone_number']
    success_url = reverse_lazy('contact_list')


# ======================
# POWER
# ======================
class PowerView(TemplateView):
    template_name = 'services/power.html'


def power_data(request):
    logs = PowerLog.objects.order_by('-timestamp')[:10]

    return JsonResponse({
        "labels": [l.timestamp.strftime("%H:%M:%S") for l in logs][::-1],
        "voltage": [l.voltage for l in logs][::-1],
        "current": [l.current for l in logs][::-1],
        "power": [l.power for l in logs][::-1],
    })