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
    PowerCreateView,
    power_data
)

urlpatterns = [

    # ======================
    # FULL PAGE
    # ======================
    path('', DashboardView.as_view(), name='dashboard'),

    # SERVICE
    path('services/', ServiceListView.as_view(), name='service_list'),
    path('services/add/', ServiceCreateView.as_view(), name='service_create'),

    # CONTACT
    path('contacts/', ContactListView.as_view(), name='contact_list'),
    path('contacts/add/', ContactCreateView.as_view(), name='contact_create'),

    # ======================
    # POWER (FIXED ⚡)
    # ======================
    path('power/', PowerView.as_view(), name='power'),
    path('power/add/', PowerCreateView.as_view(), name='power_add'),

    # API (UNTUK CHART)
    path('power/data/', power_data, name='power_data'),

    # ======================
    # SPA (AJAX LOAD)
    # ======================
    path('load-dashboard/', LoadDashboardView.as_view(), name='load_dashboard'),
    path('load-services/', LoadServiceListView.as_view(), name='load_services'),
    path('load-contacts/', LoadContactListView.as_view(), name='load_contacts'),
]