from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
# from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from djqscsv import render_to_csv_response
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanSyncingError
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.forms.dataset import DatasetForm as Form
from idgo_admin.models import Dataset
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import Mail
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.models import Resource
from idgo_admin.utils import three_suspension_points
import json


CKAN_URL = settings.CKAN_URL

decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class DatasetManager(View):

    template = 'idgo_admin/dataset.html'
    namespace = 'idgo_admin:dataset'
    namespace_resource = 'idgo_admin:resource'

    @ExceptionsHandler(ignore=[Http404])
    def get(self, request):

        user = request.user
        profile = get_object_or_404(Profile, user=user)
        form = Form(include={'user': user, 'identification': False, 'id': None})
        dataset_name = 'Nouveau'
        dataset_id = None
        dataset_ckan_slug = None
        resources = []

        # Ugly
        ckan_slug = request.GET.get('ckan_slug')
        if ckan_slug:
            instance = get_object_or_404(
                Dataset, ckan_slug=ckan_slug, editor=user)
            return redirect(
                reverse(self.namespace) + '?id={0}'.format(instance.pk))

        id = request.GET.get('id')
        if id:
            instance = get_object_or_404(Dataset, id=id, editor=user)

            if not instance.is_profile_allowed(profile):
                # return HttpResponseForbidden("L'accès à ce jeu de données est réservé")
                raise Http404

            form = Form(instance=instance,
                        include={'user': user, 'identification': True, 'id': id})
            dataset_name = instance.name
            dataset_id = instance.id
            dataset_ckan_slug = instance.ckan_slug
            resources = [(
                o.pk,
                o.name,
                o.format_type.extension,
                o.created_on.isoformat() if o.created_on else None,
                o.last_update.isoformat() if o.last_update else None,
                o.get_restricted_level_display(),
                str(o.ckan_id)
                ) for o in Resource.objects.filter(dataset=instance)]

        context = {'ckan_url': CKAN_URL,
                   'form': form,
                   'first_name': user.first_name,
                   'last_name': user.last_name,
                   'dataset_name': three_suspension_points(dataset_name),
                   'dataset_id': dataset_id,
                   'dataset_ckan_slug': dataset_ckan_slug,
                   'licenses': dict(
                       (o.pk, o.license.pk) for o
                       in LiaisonsContributeurs.get_contribs(profile=profile) if o.license),
                   'resources': json.dumps(resources),
                   'tags': json.dumps(ckan.get_tags())}

        return render(request, self.template, context=context)

    @ExceptionsHandler(ignore=[Http404])
    @transaction.atomic
    def post(self, request):

        def http_redirect(dataset_id):
            return HttpResponseRedirect(
                reverse(self.namespace) + '?id={0}'.format(dataset_id))

        user = request.user
        profile = get_object_or_404(Profile, user=user)

        context = {
            'form': None,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'dataset_name': 'Nouveau',
            'dataset_id': None,
            'licenses': dict(
                (o.pk, o.license.pk) for o
                in LiaisonsContributeurs.get_contribs(profile=profile) if o.license),
            'resources': [],
            'tags': json.dumps(ckan.get_tags())}

        id = request.POST.get('id', request.GET.get('id'))
        if id:
            instance = get_object_or_404(Dataset, id=id, editor=user)

            if not instance.is_profile_allowed(profile):
                # return HttpResponseForbidden("L'accès à ce jeu de données est réservé")
                raise Http404

            form = Form(data=request.POST, instance=instance,
                        include={'user': user, 'identification': True, 'id': id})

            if not form.is_valid():
                context.update({
                    'ckan_url': CKAN_URL,
                    'form': form,
                    'dataset_name': three_suspension_points(instance.name),
                    'dataset_ckan_slug': instance.ckan_slug,
                    'dataset_id': instance.id,
                    'resources': json.dumps([(
                        o.pk,
                        o.name,
                        o.format_type.extension,
                        o.created_on.isoformat() if o.created_on else None,
                        o.last_update.isoformat() if o.last_update else None,
                        o.get_restricted_level_display(),
                        str(o.ckan_id)
                        ) for o in Resource.objects.filter(dataset=instance)])})
                return render(request, self.template, context)

            with transaction.atomic():
                form.handle_me(request, id=id)

            messages.success(
                request, 'Le jeu de données a été mis à jour avec succès.')

            return http_redirect(instance.id)

        form = Form(data=request.POST,
                    include={'user': user, 'identification': False, 'id': None})

        if not form.is_valid():
            context.update({'form': form})
            return render(request, self.template, context)

        with transaction.atomic():
            instance = form.handle_me(request)

        messages.success(request, (
            'Le jeu de données a été créé avec succès. '
            'Souhaitez-vous <a href="{0}">créer un nouveau jeu de '
            'données ?</a> ou <a href="{1}">ajouter une ressource ?</a>'
            ).format(reverse(self.namespace),
                     reverse(self.namespace_resource,
                             kwargs={'dataset_id': instance.id})))

        return http_redirect(instance.id)

    @ExceptionsHandler(ignore=[Http404, CkanSyncingError])
    def delete(self, request):

        user = request.user
        id = request.POST.get('id', request.GET.get('id'))
        if not id:
            raise Http404
        instance = get_object_or_404(Dataset, id=id, editor=user)

        if not instance.is_profile_allowed(
                get_object_or_404(Profile, user=user)):
            # return HttpResponseForbidden("L'accès à ce jeu de données est réservé")
            return Http404

        ckan_id = str(instance.ckan_id)
        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])
        try:
            ckan_user.delete_dataset(ckan_id)
            ckan.purge_dataset(ckan_id)
        except CkanSyncingError as e:
            if e.name == 'NotFound':
                instance.delete()
            status = 500
            message = 'Impossible de supprimer le jeu de données Ckan.'
            messages.error(request, message)
        else:
            instance.delete()
            status = 200
            message = 'Le jeu de données a été supprimé avec succès.'
            messages.success(request, message)
        finally:
            ckan_user.close()

        Mail.conf_deleting_dataset_res_by_user(user, dataset=instance)

        # return render(request, 'idgo_admin/response.html',
        #               context={'message': message}, status=status)

        return HttpResponse(status=status)


@ExceptionsHandler(ignore=[Http404])
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def datasets(request):

    user = request.user
    profile = get_object_or_404(Profile, user=user)

    datasets = [(
        o.pk,
        o.name,
        o.date_creation.isoformat() if o.date_creation else None,
        o.date_modification.isoformat() if o.date_modification else None,
        o.date_publication.isoformat() if o.date_publication else None,
        Organisation.objects.get(id=o.organisation_id).name,
        o.published,
        o.is_inspire,
        o.ckan_slug,
        profile in LiaisonsContributeurs.get_contributors(o.organisation)
        ) for o in Dataset.objects.filter(editor=user)]

    my_contributions = \
        LiaisonsContributeurs.get_contribs(profile=profile)

    awaiting_contributions = \
        [c.name for c in LiaisonsContributeurs.get_pending(profile=profile)]

    return render(request, 'idgo_admin/home.html',
                  {'ckan_url': CKAN_URL,
                   'first_name': user.first_name,
                   'last_name': user.last_name,
                   'datasets': json.dumps(datasets),
                   'is_contributor': json.dumps(len(my_contributions) > 0),
                   'awaiting_contributions': awaiting_contributions},
                  status=200)


@ExceptionsHandler(ignore=[Http404])
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def export(request):
    f = request.GET.get('format')
    if f == 'csv':
        return render_to_csv_response(Dataset.objects.filter(
            editor=request.user))

    raise Http404
