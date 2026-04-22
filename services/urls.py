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

    # ======================
    # SPA (AJAX LOAD)
    # ======================
    path('load-dashboard/', LoadDashboardView.as_view()),
    path('load-services/', LoadServiceListView.as_view()),
    path('load-contacts/', LoadContactListView.as_view()),
]