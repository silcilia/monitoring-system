from django.urls import path
from .views import (

    # ======================
    # WEB
    # ======================
    DashboardView,
    ServiceListView,
    ServiceCreateView,
    ServiceUpdateView,
    ServiceDeleteView,

    ContactListView,
    ContactCreateView,
    ContactUpdateView,
    ContactDeleteView,

    PowerView,
    LoginPageView,

    # ======================
    # API AUTH
    # ======================
    LoginAPI,
    LogoutAPI,
    RegisterAPI,

    # ======================
    # API DASHBOARD
    # ======================
    DashboardAPI,

    # ======================
    # API SERVICES
    # ======================
    ServiceAPI,
    ServiceDetailAPI,

    # ======================
    # API CONTACT
    # ======================
    ContactAPI,
    ContactDetailAPI,

    # ======================
    # API POWER
    # ======================
    PowerDataAPI,
    PowerCreateAPI,
)

urlpatterns = [

    # ======================
    # AUTH (WEB)
    # ======================
    path('login/', LoginPageView.as_view(), name='login'),

    # ======================
    # DASHBOARD (WEB)
    # ======================
    path('', DashboardView.as_view(), name='home'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),

    # ======================
    # SERVICES (WEB)
    # ======================
    path('services/', ServiceListView.as_view(), name='service_list'),
    path('services/add/', ServiceCreateView.as_view(), name='service_create'),
    path('services/edit/<int:pk>/', ServiceUpdateView.as_view(), name='service_update'),
    path('services/delete/<int:pk>/', ServiceDeleteView.as_view(), name='service_delete'),

    # ======================
    # CONTACTS (WEB)
    # ======================
    path('contacts/', ContactListView.as_view(), name='contact_list'),
    path('contacts/add/', ContactCreateView.as_view(), name='contact_create'),
    path('contacts/edit/<int:pk>/', ContactUpdateView.as_view(), name='contact_update'),
    path('contacts/delete/<int:pk>/', ContactDeleteView.as_view(), name='contact_delete'),

    # ======================
    # POWER (WEB)
    # ======================
    path('power/', PowerView.as_view(), name='power'),

    # =====================================================
    # AUTH API
    # =====================================================
    path('api/login/', LoginAPI.as_view(), name='api_login'),
    path('api/register/', RegisterAPI.as_view(), name='api_register'),
    path('api/logout/', LogoutAPI.as_view(), name='api_logout'),

    # =====================================================
    # DASHBOARD API
    # =====================================================
    path('api/dashboard/', DashboardAPI.as_view(), name='api_dashboard'),

    # =====================================================
    # SERVICE API
    # =====================================================
    path('api/services/', ServiceAPI.as_view(), name='api_services'),
    path('api/services/<int:pk>/', ServiceDetailAPI.as_view(), name='api_service_detail'),

    # =====================================================
    # CONTACT API
    # =====================================================
    path('api/contacts/', ContactAPI.as_view(), name='api_contacts'),
    path('api/contacts/<int:pk>/', ContactDetailAPI.as_view(), name='api_contact_detail'),

    # =====================================================
    # POWER API
    # =====================================================
    path('api/power-data/', PowerDataAPI.as_view(), name='api_power_data'),
    path('api/power-add/', PowerCreateAPI.as_view(), name='api_power_add'),
]