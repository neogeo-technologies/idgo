from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from idgo_admin.models import *
from profiles.ckan_module import CkanHandler as ckan, \
                                 CkanUserHandler as ckan_me
from .forms.dataset import DatasetForm


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


def render_on_error(request, dform=DatasetForm()):
    return render(request, 'idgo_admin/dataset.html', {'dform': dform})


def render_an_critical_error(request):
    message = "Une erreur critique s'est produite lors de la suppression " \
              "du jeu de donnée. "

    return JsonResponse(data={'error':message}, status=400)


@method_decorator(decorators, name='dispatch')
class DatasetManager(View):

    def get(self, request):

        id = request.GET.get('id') or None
        if id:
            dataset = get_object_or_404(
                                Dataset, id=id, editor=request.user)
            return render(request, 'idgo_admin/dataset.html',
                          {'dform': DatasetForm(instance=dataset)})

        return render(request, 'idgo_admin/dataset.html',
                      {'dform': DatasetForm()})

    def post(self, request):

        id = request.POST.get('id', request.GET.get('id')) or None
        if id:
            dataset = get_object_or_404(Dataset, id=id, editor=request.user)
            dform = DatasetForm(instance=dataset, data=request.POST)
            if not dform.is_valid() or not request.user.is_authenticated:
                return render(request, 'idgo_admin/dataset.html',
                              {'dform': DatasetForm(instance=dataset)})

            dform.handle_me(request, id)
            message = 'Le jeux de données a été mis à jour avec succès.'
            return render(request, 'profiles/success.html',
                          {'message': message}, status=200)


        dform = DatasetForm(data=request.POST)
        if dform.is_valid() and request.user.is_authenticated:
            dform.handle_me(request, id=request.GET.get('id'))

            message = 'Le jeux de données a été crée avec succès.'
            return render(request, 'profiles/success.html',
                          {'message': message}, status=200)

        return render_on_error(request, dform)

    def delete(self, request):

        id = request.POST.get('id', request.GET.get('id')) or None
        if not id:
            return render_an_critical_error(request)

        dataset = get_object_or_404(Dataset, id=id, editor=request.user)

        ckan_user = ckan_me(ckan.get_user(request.user.username)['apikey'])
        try:
            ckan_user.delete_dataset(dataset.ckan_id, purge=True)
        except:
            pass
        ckan_user.close()

        dataset.delete()

        message = 'Le jeux de données a été supprimé avec succès.'
        return JsonResponse(data={'success':message}, status=200)
