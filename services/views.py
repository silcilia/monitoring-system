from django.shortcuts import render, redirect
from .models import Service, Contact

# ======================
# SERVICE
# ======================

def service_list(request):
    services = Service.objects.all()
    return render(request, 'services/service_list.html', {'services': services})


def service_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        url = request.POST.get('url')
        service_type = request.POST.get('service_type')

        Service.objects.create(
            name=name,
            url=url,
            service_type=service_type
        )
        return redirect('service_list')

    return render(request, 'services/service_form.html')


# ======================
# CONTACT
# ======================

def contact_list(request):
    contacts = Contact.objects.all()
    return render(request, 'services/contact_list.html', {'contacts': contacts})


def contact_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')

        Contact.objects.create(
            name=name,
            phone_number=phone
        )
        return redirect('contact_list')

    return render(request, 'services/contact_form.html')
