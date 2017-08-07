from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.forms.dataset import DatasetForm as Form
from idgo_admin.models import Dataset
from idgo_admin.models import Liaisons_Contributeurs
from idgo_admin.models import Mail
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.models import Resource
import json
import urllib


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class DatasetManager(View):

    def redirect_url_with_querystring(self, request, text, path,
                                      successfull=True, **kwargs):
        if successfull:
            messages.success(request, text)
        else:
            messages.error(request, text)
        return HttpResponseRedirect(path + '?' + urllib.parse.urlencode(kwargs))

    def get(self, request):

        user = request.user
        form = Form(include={'user': user, 'identification': False})
        dataset_name = 'Nouveau'
        dataset_id = None
        resources = []

        # Ugly
        ckan_slug = request.GET.get('ckan_slug') or None
        if ckan_slug:
            instance = get_object_or_404(
                Dataset, ckan_slug=ckan_slug, editor=user)
            return redirect('{0}{1}'.format(reverse('idgo_admin:dataset'),
                            '?id={0}'.format(instance.pk)))

        id = request.GET.get('id') or None
        if id:
            instance = get_object_or_404(Dataset, id=id, editor=user)
            form = Form(instance=instance,
                        include={'user': user, 'identification': True})
            dataset_name = instance.name
            dataset_id = instance.id
            resources = [(
                o.pk,
                o.name,
                o.data_format,
                o.created_on.isoformat() if o.created_on else None,
                o.last_update.isoformat() if o.last_update else None,
                o.get_restricted_level_display()
                ) for o in Resource.objects.filter(dataset=instance)]

        context = {'form': form,
                   'first_name': user.first_name,
                   'last_name': user.last_name,
                   'dataset_name': dataset_name,
                   'dataset_id': dataset_id,
                   'resources': json.dumps(resources),
                   'tags': json.dumps(ckan.get_tags())}

        return render(request, 'idgo_admin/dataset.html', context=context)

    def post(self, request):

        user = request.user
        dataset_id = None
        success = False
        text = "Erreur lors de l'opération de modification de la base Dataset"

        id = request.POST.get('id', request.GET.get('id')) or None
        if id:
            instance = get_object_or_404(Dataset, id=id, editor=user)
            form = Form(
                data=request.POST, instance=instance,
                include={'user': user, 'identification': True})
            dataset_id = instance.id

            if not form.is_valid():
                return render(request, 'idgo_admin/dataset.html',
                              {'form': form})

            if request.user.is_authenticated:
                try:
                    form.handle_me(request, id=id)
                except Exception as e:
                    success = False
                    text = ("L'erreur suivante est survenue : "
                            '<strong>{0}</strong>.').format(str(e))
                else:
                    success = True
                    text = 'Le jeu de données a été mis à jour avec succès.'

                return self.redirect_url_with_querystring(
                    request, text, reverse('idgo_admin:dataset'),
                    successfull=success, id=dataset_id)

        else:
            form = Form(data=request.POST,
                        include={'user': user, 'identification': False})
            if not form.is_valid():
                return render(request, 'idgo_admin/dataset.html', {'form': form})

            if request.user.is_authenticated:
                try:
                    instance = form.handle_me(request)
                except Exception as e:
                    messages.error = ("L'erreur suivante est survenue : "
                                      '<strong>{0}</strong>.').format(str(e))
                    return render(
                        request, 'idgo_admin/dataset.html', {'form': form})
                else:
                    success = True
                    text = (
                        'Le jeu de données a été créé avec succès. '
                        'Souhaitez-vous <a href="{0}">créer un nouveau jeu de données ?</a>'
                        ).format(reverse('idgo_admin:dataset'))
                    form = Form(instance=instance, include={'user': user})
                    dataset_id = instance.id

            return self.redirect_url_with_querystring(
                request, text, reverse('idgo_admin:dataset'),
                successfull=success, id=dataset_id)

    def delete(self, request):

        user = request.user
        id = request.POST.get('id', request.GET.get('id')) or None
        if not id:
            return Http404()
        dataset = get_object_or_404(Dataset, id=id, editor=user)

        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])
        try:
            ckan_user.delete_dataset(str(dataset.ckan_id))
            ckan.purge_dataset(str(dataset.ckan_id))
        except Exception:
            # TODO Gérer les erreurs correctement
            message = "Le jeu de données <strong>{0}</strong> ne peut pas être "\
                      "supprimé de CKAN. Merci de contacter l'administrateur du site.".format(dataset.name)
            status = 400
        else:
            dataset.delete()
            message = 'Le jeu de données <strong>{0}</strong> a été supprimé avec succès.'.format(dataset.name)
            status = 200
        ckan_user.close()

        try:
            Mail.conf_deleting_dataset_res_by_user(user, dataset=dataset)
        except Exception:
            # TODO Que faire en cas d'erreur à ce niveau ?
            pass

        context = {'message': message,
                   'action': '{0}#datasets'.format(reverse('idgo_admin:home'))}

        return render(
            request, 'idgo_admin/response.html', context=context, status=status)


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def datasets(request):

    user = request.user
    datasets = [(
        o.pk,
        o.name,
        o.date_creation.isoformat() if o.date_creation else None,
        o.date_modification.isoformat() if o.date_modification else None,
        o.date_publication.isoformat() if o.date_publication else None,
        Organisation.objects.get(id=o.organisation_id).name,
        o.published) for o in Dataset.objects.filter(editor=user)]

    # TODO Déplacer dans SignIn ###############################################
    try:
        profile = Profile.objects.get(user=user)
    except Exception:
        logout(request)
        return redirect('idgo_admin:signIn')
    ###########################################################################

    my_contributions = Liaisons_Contributeurs.get_contribs(profile=profile)
    is_contributor = len(my_contributions) > 0

    return render(request, 'idgo_admin/home.html',
                  {'first_name': user.first_name,
                   'last_name': user.last_name,
                   'datasets': json.dumps(datasets),
                   'is_contributor': json.dumps(is_contributor)},
                  status=200)
