from django.db import models

# =========================
# SERVICE
# =========================
class Service(models.Model):
    STATUS_CHOICES = [
        ('UP', 'UP'),
        ('DOWN', 'DOWN'),
    ]

    TYPE_CHOICES = [
        ('HTTP', 'HTTP'),
        ('PING', 'PING'),
    ]

    name = models.CharField(max_length=100)
    url = models.CharField(max_length=255)
    service_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    last_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='UP')

    def __str__(self):
        return self.name


# =========================
# CONTACT
# =========================
class Contact(models.Model):
    CHANNEL_CHOICES = [
        ('WA', 'WhatsApp'),
    ]

    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default='WA')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# =========================
# RELASI SERVICE - CONTACT (MANY TO MANY)
# =========================
class ServiceContact(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.service.name} - {self.contact.name}"


# =========================
# LOG MONITORING SERVICE
# =========================
class Log(models.Model):
    STATUS_CHOICES = [
        ('UP', 'UP'),
        ('DOWN', 'DOWN'),
    ]

    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.service.name} - {self.status}"


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
# POWER LOG (DATA LISTRIK)
# =========================
class PowerLog(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    voltage = models.FloatField()
    current = models.FloatField()
    power = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.device.name} - {self.voltage}V"
