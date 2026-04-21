from django.contrib import admin
from .models import Service, Contact, ServiceContact, Log, Device, PowerLog

admin.site.register(Service)
admin.site.register(Contact)
admin.site.register(ServiceContact)
admin.site.register(Log)
admin.site.register(Device)
admin.site.register(PowerLog)
