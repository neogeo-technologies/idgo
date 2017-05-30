from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from idgo_admin.models import *
from .forms.dataset import DatasetForm


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


def render_on_error(request, dform=DatasetForm()):
    return render(request, 'idgo_admin/dataset.html', {'dform': dform})


@method_decorator(decorators, name='dispatch')
class DatasetManager(View):

    def get(self, request):
        id = request.GET.get('id')
        dataset = id and get_object_or_404(
                            Dataset, id=id, editor=request.user) or None

        return render(request, 'idgo_admin/dataset.html',
                      {'dform': DatasetForm(instance=dataset)})

    def post(self, request):

        dform = DatasetForm(data=request.POST)
        if dform.is_valid() and request.user.is_authenticated:
            dform.handle_dataset(request, id=request.GET.get('id'))

            message = 'Le jeux de données a été mis à jour avec succès.'
            return render(request, 'profiles/success.html',
                          {'message': message}, status=200)

        return render_on_error(request, dform)
