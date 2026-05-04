from django.db import models


# =========================
# SERVICE
# =========================
class Service(models.Model):
    STATUS_CHOICES = [
        ('UP', 'UP'),
        ('DOWN', 'DOWN'),
        ('UNKNOWN', 'UNKNOWN'),
    ]

    TYPE_CHOICES = [
        ('HTTP', 'HTTP'),
        ('PING', 'PING'),
    ]

    name = models.CharField(max_length=100)
    url = models.CharField(max_length=255)
    service_type = models.CharField(max_length=10, choices=TYPE_CHOICES)

    # 🔥 STATUS TERAKHIR
    last_status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='UNKNOWN'
    )

    # 🔥 WAKTU TERAKHIR CEK
    last_checked = models.DateTimeField(null=True, blank=True)

    # 🔥 PENYEBAB DOWN (HTTP 500 / timeout / dll)
    last_down_reason = models.CharField(max_length=255, null=True, blank=True)

    # 🔥 ANTI SPAM NOTIF
    last_notified = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.service_type})"


# =========================
# CONTACT
# =========================
class Contact(models.Model):
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# =========================
# RELASI SERVICE - CONTACT
# =========================
class ServiceContact(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.service.name} -> {self.contact.name}"


# =========================
# LOG SERVICE (HISTORY)
# =========================
class Log(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    status = models.CharField(max_length=10)
    message = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.service.name} - {self.status} - {self.timestamp}"


# =========================
# DEVICE (IOT)
# =========================
class Device(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    threshold_voltage = models.FloatField()
    threshold_current = models.FloatField()

    def __str__(self):
        return self.name


# =========================
# RELASI DEVICE - CONTACT
# =========================
class DeviceContact(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.device.name} -> {self.contact.name}"


# =========================
# POWER LOG
# =========================
class PowerLog(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    voltage = models.FloatField()
    current = models.FloatField()
    power = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.device.name} - {self.power}W"