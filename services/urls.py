from django.urls import path
from .views import (
    DashboardView,
    ServiceListView,
    ServiceCreateView,
    ContactListView,
    ContactCreateView,
    LoadDashboardView,
    LoadServiceListView,
    LoadContactListView,
    PowerView,
    power_data
)

urlpatterns = [

    # ======================
    # FULL PAGE
    # ======================
    path('', DashboardView.as_view(), name='dashboard'),

    path('services/', ServiceListView.as_view(), name='service_list'),
    path('services/add/', ServiceCreateView.as_view(), name='service_create'),

    path('contacts/', ContactListView.as_view(), name='contact_list'),
    path('contacts/add/', ContactCreateView.as_view(), name='contact_create'),

    # POWER PAGE
    path('power/', PowerView.as_view(), name='power'),

    # ======================
    # SPA (AJAX LOAD)
    # ======================
    path('load-dashboard/', LoadDashboardView.as_view(), name='load_dashboard'),
    path('load-services/', LoadServiceListView.as_view(), name='load_services'),
    path('load-contacts/', LoadContactListView.as_view(), name='load_contacts'),

    # ======================
    # API (UNTUK GRAFIK)
    # ======================
    path('api/power-data/', power_data, name='power_data'),
]