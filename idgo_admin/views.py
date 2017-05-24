from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView

from .forms.dataset import DatasetForm, DatasetDisplayForm
from idgo_admin.models import *

def render_on_error(request, dform=DatasetForm()):
    return render(request, 'profiles/dataset.html', {'dform': dform})


@method_decorator(csrf_exempt, name='dispatch')
class DatasetCreateV(View):

    def get(self, request):

        return render(request, 'idgo_admin/dataset.html',
                      {'dform': DatasetForm()})

    def post(self, request):

        dform = DatasetForm(data=request.POST or None)
        if not dform.is_valid():
            return render_on_error(request, dform)

        try:
            with transaction.atomic():
                dataset = dform.integrate_in_bo(request)
        except IntegrityError:
            return render_on_error()

        message = "dataset has been setup"
        return render(request, 'profiles/success.html',
                      {'message': message}, status=200)


@method_decorator(csrf_exempt, name='dispatch')
class DatasetDisplayV(View):

    def get(self, request):
        from django.core import serializers

        user = request.user
        dataset = serializers.serialize("json", Dataset.objects.filter(editor=user))

        return JsonResponse(data=dataset, status=200, safe=False)