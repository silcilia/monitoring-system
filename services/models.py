from django.db import models
from django.utils import timezone


# =========================
# SERVICE
# =========================
class Service(models.Model):
    STATUS_CHOICES = [
        ('UP', 'UP'),
        ('DOWN', 'DOWN'),
        ('DEGRADED', 'DEGRADED'),
        ('UNKNOWN', 'UNKNOWN'),
    ]

    TYPE_CHOICES = [
        ('HTTP', 'HTTP'),
        ('PING', 'PING'),
    ]

    DOWN_REASON_CHOICES = [
        ('NETWORK_UNREACHABLE', 'Jaringan Down Total'),
        ('TIMEOUT', 'Request Timeout (Lemot)'),
        ('HTTP_400', 'Bad Request (400)'),
        ('HTTP_401', 'Unauthorized (401)'),
        ('HTTP_403', 'Forbidden (403)'),
        ('HTTP_404', 'Not Found (404)'),
        ('HTTP_500', 'Internal Server Error (500)'),
        ('HTTP_502', 'Bad Gateway (502)'),
        ('HTTP_503', 'Service Unavailable (503)'),
        ('HTTP_504', 'Gateway Timeout (504)'),
        ('CONNECTION_REFUSED', 'Koneksi Ditolak'),
        ('SSL_ERROR', 'SSL Certificate Error'),
        ('DNS_ERROR', 'DNS Resolution Failed'),
        ('UNKNOWN_ERROR', 'Unknown Error'),
    ]

    name = models.CharField(max_length=100)
    url = models.CharField(max_length=255)
    service_type = models.CharField(max_length=10, choices=TYPE_CHOICES)

    # STATUS TERAKHIR
    last_status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='UNKNOWN'
    )

    # WAKTU TERAKHIR CEK
    last_checked = models.DateTimeField(null=True, blank=True)

    # 🔥 PERBAIKI: Tambah max_length=255
    last_down_reason = models.CharField(
        max_length=255,  # dari 50 jadi 255
        choices=DOWN_REASON_CHOICES,
        null=True,
        blank=True
    )

    # 🔥 PERBAIKI: Tambah max_length=255
    last_down_detail = models.CharField(max_length=500, null=True, blank=True)

    # 🔥 STATUS CODE HTTP
    last_status_code = models.IntegerField(null=True, blank=True)

    # 🔥 WAKTU RESPON
    last_response_time = models.FloatField(null=True, blank=True)

    # ANTI SPAM NOTIF
    last_notified = models.DateTimeField(null=True, blank=True)
    
    # COOLDOWN NOTIF
    notification_cooldown_minutes = models.IntegerField(default=30)

    # UPTIME PERCENTAGE
    uptime_percentage = models.FloatField(default=100.0)

    def __str__(self):
        return f"{self.name} ({self.service_type})"
    
    def needs_notification(self):
        if not self.last_notified:
            return True
        from datetime import timedelta
        from django.utils import timezone
        cooldown = timedelta(minutes=self.notification_cooldown_minutes)
        return timezone.now() > self.last_notified + cooldown


# =========================
# CONTACT
# =========================
class Contact(models.Model):
    NOTIF_CHANNEL_CHOICES = [
        ('WHATSAPP', 'WhatsApp'),
        ('EMAIL', 'Email'),
        ('BOTH', 'WhatsApp & Email'),
    ]
    
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(max_length=100, null=True, blank=True)
    notification_channel = models.CharField(
        max_length=10,
        choices=NOTIF_CHANNEL_CHOICES,
        default='WHATSAPP'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
    status_code = models.IntegerField(null=True, blank=True)
    response_time = models.FloatField(null=True, blank=True)
    down_reason = models.CharField(max_length=255, null=True, blank=True)  # 🔥 PERBAIKI max_length
    message = models.CharField(max_length=500, null=True, blank=True)  # 🔥 PERBAIKI max_length
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.service.name} - {self.status} - {self.timestamp}"


# =========================
# DEVICE (IOT)
# =========================
class Device(models.Model):
    STATUS_CHOICES = [
        ('ONLINE', 'Online'),
        ('OFFLINE', 'Offline'),
        ('DEGRADED', 'Degraded'),
    ]
    
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    threshold_voltage = models.FloatField()
    threshold_current = models.FloatField()
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ONLINE')
    last_seen = models.DateTimeField(null=True, blank=True)
    has_power_backup = models.BooleanField(default=False)
    
    # WiFi dinamis
    wifi_ssid = models.CharField(max_length=100, blank=True, null=True)
    wifi_config_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.name} - {self.location}"
    
    def is_offline(self):
        if not self.last_seen:
            return True
        from datetime import timedelta
        from django.utils import timezone
        return timezone.now() > self.last_seen + timedelta(minutes=5)


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


# =========================
# NOTIFICATION LOG
# =========================
class NotificationLog(models.Model):
    CHANNEL_CHOICES = [
        ('WHATSAPP', 'WhatsApp'),
        ('EMAIL', 'Email'),
    ]
    
    TYPE_CHOICES = [
        ('SERVICE_DOWN', 'Service Down'),
        ('SERVICE_RECOVER', 'Service Recover'),
        ('DEVICE_OFFLINE', 'Device Offline'),
        ('DEVICE_ONLINE', 'Device Online'),
        ('THRESHOLD_WARNING', 'Threshold Warning'),
    ]
    
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    recipient = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_sent = models.BooleanField(default=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.notification_type} to {self.recipient} at {self.sent_at}"