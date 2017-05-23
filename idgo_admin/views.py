from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .forms.dataset import DatasetForm
from django.db import IntegrityError, transaction

def render_on_error(request, dform=DatasetForm()):
    return render(request, 'profiles/dataset.html', {'dform': dform})

@csrf_exempt
def dataset(request):

    if request.method == 'GET':
        return render(request, 'idgo_admin/dataset.html',
                      {'dform': DatasetForm()})

    dform = DatasetForm(data=request.POST or None)
    if not dform.is_valid():
        return render_on_error(request, dform)

    try:
        with transaction.atomic():
            dataset = dform.integrate_in_bo(request)

    except IntegrityError:
        return render_on_error()
    print(dataset.name)
    message = "dataset has been setup"
    return render(request, 'profiles/success.html',
                  {'message': message}, status=200)
