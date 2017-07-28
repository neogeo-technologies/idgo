from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.forms.dataset import DatasetForm as Form
from idgo_admin.models import Dataset
from idgo_admin.models import Mail
from idgo_admin.models import Resource
import json


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


def render_on_error(request):
    form = Form(include={'user': request.user})
    return render(request, 'idgo_admin/dataset.html', {'form': form})


def render_an_critical_error(request):
    message = ("Une erreur critique s'est produite "
               'lors de la suppression du jeu de donnée.')

    return JsonResponse(data={'message': message}, status=400)


@method_decorator(decorators, name='dispatch')
class DatasetManager(View):

    def get(self, request):

        user = request.user
        form = Form(include={'user': user})
        dataset_name = 'Nouveau'
        dataset_id = None
        resources = []

        id = request.GET.get('id') or None
        if id:
            instance = get_object_or_404(Dataset, id=id, editor=user)
            form = Form(instance=instance, include={'user': user})
            dataset_name = instance.name
            dataset_id = instance.id
            resources = [(
                o.pk,
                o.name,
                o.data_format,
                o.created_on.isoformat() if o.created_on else None,
                o.last_update.isoformat() if o.last_update else None,
                o.restricted_level) for o in Resource.objects.filter(dataset=instance)]

        context = {'form': form,
                   'first_name': user.first_name,
                   'last_name': user.last_name,
                   'dataset_name': dataset_name,
                   'dataset_id': dataset_id,
                   'resources': json.dumps(resources),
                   'tags': json.dumps(ckan.get_tags())}

        return render(
            request, 'idgo_admin/dataset.html', context=context)

    def post(self, request):

        user = request.user
        dataset_id = None
        resources = []
        success = False
        text = "Erreur lors de l'opération de modification de la base Dataset"
        id = request.POST.get('id', request.GET.get('id')) or None
        if id:
            instance = get_object_or_404(Dataset, id=id, editor=user)

            form = Form(
                data=request.POST, instance=instance, include={'user': user})

            dataset_name = instance.name
            dataset_id = instance.id
            resources = [(
                o.pk,
                o.name,
                o.data_format,
                o.created_on.isoformat() if o.created_on else None,
                o.last_update.isoformat() if o.last_update else None,
                o.restricted_level) for o in Resource.objects.filter(dataset=instance)]

            if form.is_valid() or request.user.is_authenticated:
                try:
                    form.handle_me(request, id=id)
                except Exception as e:
                    success = False
                    text = ("L'erreur suivante est survenue : "
                            '<strong>{0}</strong>.').format(str(e))
                else:
                    success = True
                    text = 'Le jeu de données a été mis à jour avec succès.'

        else:
            dataset_name = 'Nouveau'
            form = Form(data=request.POST, include={'user': user})
            if form.is_valid() and request.user.is_authenticated:
                try:
                    instance = form.handle_me(request)
                except Exception as e:
                    print('Exception:', e)
                    success = False
                    text = ("L'erreur suivante est survenue : "
                            '<strong>{0}</strong>.').format(str(e))
                else:
                    success = True
                    text = 'Le jeu de données a été créé avec succès.'
                    form = Form(instance=instance, include={'user': user})
                    dataset_name = instance.name
                    dataset_id = instance.id

        context = {
            'form': form,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'dataset_name': dataset_name,
            'dataset_id': dataset_id,
            'resources': json.dumps(resources),
            'tags': json.dumps(ckan.get_tags()),
            'message': {
                'status': success and 'success' or 'failure',
                'text': text}}

        return render(
            request, 'idgo_admin/dataset.html', context=context)

    def delete(self, request):

        user = request.user

        id = request.POST.get('id', request.GET.get('id')) or None
        if not id:
            return render_an_critical_error(request)

        dataset = get_object_or_404(Dataset, id=id, editor=user)
        name = dataset.name

        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])
        try:
            ckan_user.delete_dataset(str(dataset.ckan_id))
            ckan.purge_dataset(str(dataset.ckan_id))
        except Exception:
            dataset.delete()  # TODO
            message = ('Le jeu de données <strong>{0}</strong> '
                       'ne peut pas être supprimé.').format(name)
            status = 400
        else:
            dataset.delete()
            message = ('Le jeu de données <strong>{0}</strong> '
                       'a été supprimé avec succès.').format(name)
            status = 200

        try:
            Mail.conf_deleting_dataset_res_by_user(user, dataset=dataset)
        except Exception:
            pass
        ckan_user.close()

        context = {
            'message': message,
            'action': '{0}#datasets'.format(reverse('idgo_admin:home'))}

        return render(
            request, 'idgo_admin/response.htm', context=context, status=status)
