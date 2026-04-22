from django.http import JsonResponse
from services.models import Device, PowerLog
import json
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def receive_power(request):
    if request.method == 'POST':
        data = json.loads(request.body)

        try:
            device = Device.objects.get(id=data['device_id'])
        except Device.DoesNotExist:
            return JsonResponse({'error': 'Device tidak ditemukan'}, status=404)

        PowerLog.objects.create(
            device=device,
            voltage=data['voltage'],
            current=data['current'],
            power=data['power']
        )

        return JsonResponse({'status': 'ok'})