from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from .views import *

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
    # AUTH API (csrf_exempt)
    # =====================================================
    path('api/login/', csrf_exempt(LoginAPI.as_view()), name='api_login'),
    path('api/register/', csrf_exempt(RegisterAPI.as_view()), name='api_register'),
    path('api/logout/', csrf_exempt(LogoutAPI.as_view()), name='api_logout'),

    # =====================================================
    # DASHBOARD API (csrf_exempt)
    # =====================================================
    path('api/dashboard/', csrf_exempt(DashboardAPI.as_view()), name='api_dashboard'),

    # =====================================================
    # SERVICE API (csrf_exempt)
    # =====================================================
    path('api/services/', csrf_exempt(ServiceAPI.as_view()), name='api_services'),
    path('api/services/<int:pk>/', csrf_exempt(ServiceDetailAPI.as_view()), name='api_service_detail'),

    # =====================================================
    # CONTACT API (csrf_exempt)
    # =====================================================
    path('api/contacts/', csrf_exempt(ContactAPI.as_view()), name='api_contacts'),
    path('api/contacts/<int:pk>/', csrf_exempt(ContactDetailAPI.as_view()), name='api_contact_detail'),

    # =====================================================
    # POWER API (csrf_exempt)
    # =====================================================
    path('api/power-data/', csrf_exempt(PowerDataAPI.as_view()), name='api_power_data'),
    path('api/power-add/', csrf_exempt(PowerCreateAPI.as_view()), name='api_power_add'),
    path('api/check-auth/', CheckAuthAPI.as_view(), name='check_auth'),
    path('api/debug-session/', DebugSessionAPI.as_view(), name='debug_session'),
]