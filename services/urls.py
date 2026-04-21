from django.urls import path
from . import views

urlpatterns = [
    path('services/', views.service_list, name='service_list'),
    path('services/add/', views.service_create, name='service_create'),

    path('contacts/', views.contact_list, name='contact_list'),
    path('contacts/add/', views.contact_create, name='contact_create'),
]