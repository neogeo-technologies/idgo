from .forms.dataset import DatasetForm
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.models import Dataset
from profiles.ckan_module import CkanHandler as ckan
from profiles.ckan_module import CkanUserHandler as ckan_me


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


def render_on_error(request):
    dform = DatasetForm(include={'user': request.user})
    return render(request, 'idgo_admin/dataset.html', {'dform': dform})


def render_an_critical_error(request):
    message = ("Une erreur critique s'est produite "
               'lors de la suppression du jeu de donnée.')

    return JsonResponse(data={'message': message}, status=400)


@method_decorator(decorators, name='dispatch')
class DatasetManager(View):

    def get(self, request):
        user = request.user
        id = request.GET.get('id') or None
        if id:
            dataset = get_object_or_404(Dataset, id=id, editor=user)
            return render(request, 'idgo_admin/dataset.html',
                          {'first_name': user.first_name,
                           'last_name': user.last_name,
                           'dform': DatasetForm(
                               instance=dataset,
                               include={'user': request.user})})

        return render(request, 'idgo_admin/dataset.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'dform': DatasetForm(include={'user': user})})

    def post(self, request):
        user = request.user
        id = request.POST.get('id', request.GET.get('id')) or None
        if id:
            dataset = get_object_or_404(Dataset, id=id, editor=user)
            dform = DatasetForm(instance=dataset,
                                data=request.POST,
                                include={'user': user})

            if not dform.is_valid() or not request.user.is_authenticated:
                return render(request, 'idgo_admin/dataset.html',
                              {'first_name': user.first_name,
                               'last_name': user.last_name,
                               'dform': DatasetForm(instance=dataset,
                                                    include={'user': user})})

            try:
                dform.handle_me(request, id)
            except Exception as e:
                message = ("L'erreur suivante est survenue : "
                           '<strong>{0}</strong>.').format(str(e))
            else:
                message = 'Le jeu de données a été mis à jour avec succès.'

            return render(request, 'profiles/information.html',
                          {'message': message}, status=200)
        else:
            dform = DatasetForm(
                data=request.POST, include={'user': request.user})
            if dform.is_valid() and request.user.is_authenticated:
                try:
                    dform.handle_me(request, id=request.GET.get('id'))
                except Exception as e:
                    message = ("L'erreur suivante est survenue : "
                               '<strong>{0}</strong>.').format(str(e))
                else:
                    message = 'Le jeu de données a été créé avec succès.'

                return render(request, 'profiles/information.html',
                              {'message': message}, status=200)

        return render_on_error(request)

    def delete(self, request):

        id = request.POST.get('id', request.GET.get('id')) or None
        if not id:
            return render_an_critical_error(request)

        dataset = get_object_or_404(Dataset, id=id, editor=request.user)
        name = dataset.name

        ckan_user = ckan_me(ckan.get_user(request.user.username)['apikey'])
        try:
            ckan_user.delete_dataset(str(dataset.ckan_id))
            ckan.purge_dataset(str(dataset.ckan_id))
        except Exception:
            dataset.delete()
            message = ('Le jeu de données <strong>{0}</strong> '
                       'ne peut pas être supprimé.').format(name)
            status = 400
        else:
            dataset.delete()
            message = ('Le jeu de données <strong>{0}</strong> '
                       'a été supprimé avec succès.').format(name)
            status = 200

        ckan_user.close()

        return render(request, 'profiles/response.htm',
                      {'message': message}, status=status)
