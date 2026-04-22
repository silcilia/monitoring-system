from django.views.generic import ListView, CreateView, TemplateView
from .models import Service, Contact
from django.urls import reverse_lazy


# ======================
# DASHBOARD (FULL PAGE)
# ======================
class DashboardView(TemplateView):
    template_name = 'services/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        services = Service.objects.all()

        context['services'] = services
        context['total'] = services.count()
        context['up'] = services.filter(last_status='UP').count()
        context['down'] = services.filter(last_status='DOWN').count()

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
# SPA LOAD (PARTIAL VIEW)
# ======================
class LoadDashboardView(TemplateView):
    template_name = 'services/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        services = Service.objects.all()

        context['services'] = services
        context['total'] = services.count()
        context['up'] = services.filter(last_status='UP').count()
        context['down'] = services.filter(last_status='DOWN').count()

        return context


class LoadServiceListView(ListView):
    model = Service
    template_name = 'services/service_list.html'
    context_object_name = 'services'


class LoadContactListView(ListView):
    model = Contact
    template_name = 'services/contact_list.html'
    context_object_name = 'contacts'