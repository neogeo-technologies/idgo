from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .forms.dataset import DatasetForm
from idgo_admin.models import *


def render_on_error(request, dform=DatasetForm()):
    return render(request, 'idgo_admin/dataset.html', {'dform': dform})

decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class DatasetCreateV(View):

    def get(self, request):

        return render(request, 'idgo_admin/dataset.html',
                      {'dform': DatasetForm()})

    def post(self, request):

        dform = DatasetForm(data=request.POST)
        if dform.is_valid() and request.user.is_authenticated:
            try:
                with transaction.atomic():
                    if "integrate_only" in request.POST:
                        dform.handle_dataset(request, publish=False)
                    elif "publish" in request.POST:
                        dform.handle_dataset(request, publish=True)
            except IntegrityError:
                return render_on_error()

            message = "dataset has been setup"
            return render(request, 'profiles/success.html',
                          {'message': message}, status=200)

        return render_on_error(request, dform)