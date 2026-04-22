from django.urls import path
from .views import receive_power

urlpatterns = [
    path('api/power/', receive_power),
]