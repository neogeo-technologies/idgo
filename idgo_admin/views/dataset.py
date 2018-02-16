from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from djqscsv import render_to_csv_response
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanNotFoundError
from idgo_admin.ckan_module import CkanSyncingError
from idgo_admin.ckan_module import CkanTimeoutError
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.dataset import DatasetForm as Form
from idgo_admin.models import Dataset
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import Mail
from idgo_admin.models import Organisation
from idgo_admin.models import Resource
from idgo_admin.shortcuts import get_object_or_404_extended
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
from idgo_admin.utils import three_suspension_points
import json


CKAN_URL = settings.CKAN_URL
READTHEDOC_URL = settings.READTHEDOC_URL

decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class DatasetManager(View):

    template = 'idgo_admin/dataset.html'
    namespace = 'idgo_admin:dataset'
    namespace_resource = 'idgo_admin:resource'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)

        form = Form(include={'user': user, 'identification': False, 'id': None})
        dataset_name = 'Nouveau'
        dataset_id = None
        dataset_ckan_slug = None
        resources = []

        # Ugly
        ckan_slug = request.GET.get('ckan_slug')
        if ckan_slug:
            instance = get_object_or_404_extended(
                Dataset, user, include={'ckan_slug': ckan_slug})
            return redirect(
                reverse(self.namespace) + '?id={0}'.format(instance.pk))

        id = request.GET.get('id')
        if id:
            instance = get_object_or_404_extended(
                Dataset, user, include={'id': id})

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

        context = {'form': form,
                   'doc_url': READTHEDOC_URL,
                   'dataset_name': three_suspension_points(dataset_name),
                   'dataset_id': dataset_id,
                   'dataset_ckan_slug': dataset_ckan_slug,
                   'licenses': dict(
                       (o.pk, o.license.pk) for o
                       in LiaisonsContributeurs.get_contribs(profile=profile) if o.license),
                   'resources': json.dumps(resources),
                   'tags': json.dumps(ckan.get_tags())}

        return render_with_info_profile(request, self.template, context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    @transaction.atomic
    def post(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)

        def http_redirect(dataset):
            if 'save' in request.POST:
                namespace = dataset.editor == profile.user and 'datasets' or 'all_datasets'
                return HttpResponseRedirect('{0}#datasets/{1}'.format(
                    reverse('idgo_admin:{0}'.format(namespace)), dataset.id))
            if 'continue' in request.POST:
                return HttpResponseRedirect('{0}?id={1}'.format(
                    reverse(self.namespace), dataset.id))

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

            instance = get_object_or_404_extended(
                Dataset, user, include={'id': id})

            form = Form(request.POST, request.FILES, instance=instance,
                        include={'user': user, 'identification': True, 'id': id})

            if not form.is_valid():
                context.update({
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
                return render_with_info_profile(request, self.template, context)

            try:
                with transaction.atomic():
                    form.handle_me(request, id=id)
            except CkanSyncingError:
                messages.error(request, 'Une erreur de synchronisation avec CKAN est survenue.')
            except CkanTimeoutError:
                messages.error(request, 'Impossible de joindre CKAN.')
            else:
                messages.success(request, (
                    'Le jeu de données a été mis à jour avec succès. '
                    'Souhaitez-vous <a href="{0}/dataset/{1}" target="_blank">'
                    'voir le jeu de données dans CKAN</a> ?'
                    ).format(CKAN_URL, instance.ckan_slug))

            return http_redirect(instance)

        form = Form(request.POST, request.FILES,
                    include={'user': user, 'identification': False, 'id': None})

        if not form.is_valid():
            context.update({'form': form})
            return render_with_info_profile(request, self.template, context)

        with transaction.atomic():
            instance = form.handle_me(request)

        messages.success(request, (
            'Le jeu de données a été créé avec succès. Souhaitez-vous '
            '<a href="{0}">créer un nouveau jeu de données</a> ? ou '
            '<a href="{1}">ajouter une ressource</a> ? ou bien '
            '<a href="{2}/dataset/{3}" target="_blank">voir le jeu de données '
            'dans CKAN</a> ?'
            ).format(reverse(self.namespace),
                     reverse(self.namespace_resource,
                             kwargs={'dataset_id': instance.id}),
                     CKAN_URL, instance.ckan_slug))

        return http_redirect(instance)

    @ExceptionsHandler(ignore=[Http404, CkanSyncingError],
                       actions={ProfileHttp404: on_profile_http404})
    def delete(self, request, *args, **kwargs):

        # TODO: factoriser

        user, profile = user_and_profile(request)

        id = request.POST.get('id', request.GET.get('id'))
        if not id:
            raise Http404

        instance = get_object_or_404_extended(
            Dataset, user, include={'id': id})

        # organisation = instance.organisation

        ckan_id = str(instance.ckan_id)
        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])
        try:
            ckan_user.delete_dataset(ckan_id)
            # ckan.purge_dataset(ckan_id)  # -> purge déplacé dans 'model'
        except CkanNotFoundError:
            status = 500
            message = 'Le jeu de données CKAN est indisponible.'
            messages.error(request, message)
            # instance.delete()
        except CkanSyncingError:
            status = 500
            message = 'Impossible de supprimer le jeu de données CKAN.'
            messages.error(request, message)
        else:
            instance.delete()
            status = 200
            message = 'Le jeu de données a été supprimé avec succès.'
            messages.success(request, message)
        finally:
            ckan_user.close()

        # ckan_orga = ckan.get_organization(
        #     str(organisation.ckan_id), include_datasets=True)
        # if (ckan_orga and len(ckan_orga['packages']) == 0) \
        #         and not Dataset.objects.filter(organisation=organisation).exists():
        #     ckan.purge_organization(str(organisation.ckan_id))

        Mail.conf_deleting_dataset_res_by_user(user, dataset=instance)

        return HttpResponse(status=status)

# ???
# @method_decorator(decorators, name='dispatch')
# class ReferentDatasetManager(View):
#
#     template = 'idgo_admin/dataset.html'
#     namespace = 'idgo_admin:dataset'
#     namespace_resource = 'idgo_admin:resource'
#
#     @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
#     def get(self, request, *args, **kwargs):
#
#         user, profile = user_and_profile(request)
#
#         form = Form(include={'user': user, 'identification': False, 'id': None})
#         dataset_name = 'Nouveau'
#         dataset_id = None
#         dataset_ckan_slug = None
#         resources = []
#
#         # Ugly
#         ckan_slug = request.GET.get('ckan_slug')
#         if ckan_slug:
#             instance = get_object_or_404(
#                 Dataset, ckan_slug=ckan_slug, editor=user)
#             return redirect(
#                 reverse(self.namespace) + '?id={0}'.format(instance.pk))
#
#         id = request.GET.get('id')
#         if id:
#             instance = get_object_or_404_extended(
#                 Dataset, user, include={'id': id})
#
#             form = Form(instance=instance,
#                         include={'user': user, 'identification': True, 'id': id})
#             dataset_name = instance.name
#             dataset_id = instance.id
#             dataset_ckan_slug = instance.ckan_slug
#             resources = [(
#                 o.pk,
#                 o.name,
#                 o.format_type.extension,
#                 o.created_on.isoformat() if o.created_on else None,
#                 o.last_update.isoformat() if o.last_update else None,
#                 o.get_restricted_level_display(),
#                 str(o.ckan_id)
#                 ) for o in Resource.objects.filter(dataset=instance)]
#
#         context = {'form': form,
#                    'dataset_name': three_suspension_points(dataset_name),
#                    'dataset_id': dataset_id,
#                    'dataset_ckan_slug': dataset_ckan_slug,
#                    'licenses': dict(
#                        (o.pk, o.license.pk) for o
#                        in LiaisonsContributeurs.get_contribs(profile=profile) if o.license),
#                    'resources': json.dumps(resources),
#                    'tags': json.dumps(ckan.get_tags())}
#
#         return render_with_info_profile(request, self.template, context=context)
#
#     @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
#     @transaction.atomic
#     def post(self, request, *args, **kwargs):
#
#         def http_redirect(dataset_id):
#             return HttpResponseRedirect(
#                 reverse(self.namespace) + '?id={0}'.format(dataset_id))
#
#         user, profile = user_and_profile(request)
#
#         context = {
#             'form': None,
#             'first_name': user.first_name,
#             'last_name': user.last_name,
#             'dataset_name': 'Nouveau',
#             'dataset_id': None,
#             'licenses': dict(
#                 (o.pk, o.license.pk) for o
#                 in LiaisonsContributeurs.get_contribs(profile=profile) if o.license),
#             'resources': [],
#             'tags': json.dumps(ckan.get_tags())}
#
#         id = request.POST.get('id', request.GET.get('id'))
#         if id:
#
#             instance = get_object_or_404_extended(
#                 Dataset, user, include={'id': id})
#
#             form = Form(data=request.POST, instance=instance,
#                         include={'user': user, 'identification': True, 'id': id})
#
#             if not form.is_valid():
#                 context.update({
#                     'form': form,
#                     'dataset_name': three_suspension_points(instance.name),
#                     'dataset_ckan_slug': instance.ckan_slug,
#                     'dataset_id': instance.id,
#                     'resources': json.dumps([(
#                         o.pk,
#                         o.name,
#                         o.format_type.extension,
#                         o.created_on.isoformat() if o.created_on else None,
#                         o.last_update.isoformat() if o.last_update else None,
#                         o.get_restricted_level_display(),
#                         str(o.ckan_id)
#                         ) for o in Resource.objects.filter(dataset=instance)])})
#                 return render_with_info_profile(request, self.template, context)
#
#             with transaction.atomic():
#                 form.handle_me(request, id=id)
#
#             messages.success(
#                 request, 'Le jeu de données a été mis à jour avec succès.')
#
#             return http_redirect(instance.id)
#
#         form = Form(data=request.POST,
#                     include={'user': user, 'identification': False, 'id': None})
#
#         if not form.is_valid():
#             context.update({'form': form})
#             return render_with_info_profile(request, self.template, context)
#
#         with transaction.atomic():
#             instance = form.handle_me(request)
#
#         messages.success(request, (
#             'Le jeu de données a été créé avec succès. '
#             'Souhaitez-vous <a href="{0}">créer un nouveau jeu de '
#             'données ?</a> ou <a href="{1}">ajouter une ressource ?</a>'
#             ).format(reverse(self.namespace),
#                      reverse(self.namespace_resource,
#                              kwargs={'dataset_id': instance.id})))
#
#         return http_redirect(instance.id)
#
#     @ExceptionsHandler(ignore=[Http404, CkanSyncingError],
#                        actions={ProfileHttp404: on_profile_http404})
#     def delete(self, request, *args, **kwargs):
#
#         # TODO: factoriser
#
#         user, profile = user_and_profile(request)
#
#         id = request.POST.get('id', request.GET.get('id'))
#         if not id:
#             raise Http404
#
#         instance = get_object_or_404_extended(
#             Dataset, user, include={'id': id})
#
#         # organisation = instance.organisation
#
#         ckan_id = str(instance.ckan_id)
#         ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])
#         try:
#             ckan_user.delete_dataset(ckan_id)
#             # ckan.purge_dataset(ckan_id)  # -> purge déplacé dans 'model'
#         except CkanSyncingError as e:
#             if e.name == 'NotFound':
#                 instance.delete()
#             status = 500
#             message = 'Impossible de supprimer le jeu de données Ckan.'
#             messages.error(request, message)
#         else:
#             instance.delete()
#             status = 200
#             message = 'Le jeu de données a été supprimé avec succès.'
#             messages.success(request, message)
#         finally:
#             ckan_user.close()
#
#         # ckan_orga = ckan.get_organization(
#         #     str(organisation.ckan_id), include_datasets=True)
#         # if (ckan_orga and len(ckan_orga['packages']) == 0) \
#         #         and not Dataset.objects.filter(organisation=organisation).exists():
#         #     ckan.purge_organization(str(organisation.ckan_id))
#
#         Mail.conf_deleting_dataset_res_by_user(user, dataset=instance)
#
#         return HttpResponse(status=status)


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def datasets(request, *args, **kwargs):

    user, profile = user_and_profile(request)

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

    return render_with_info_profile(
        request, 'idgo_admin/datasets.html', status=200,
        context={'datasets': json.dumps(datasets),
                 'datasets_count': len(datasets)})


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def all_datasets(request, *args, **kwargs):

    user, profile = user_and_profile(request)
    roles = profile.get_roles()
    if not roles["is_referent"] and not roles["is_admin"]:
        raise Http404

    datasets = [(
        d.pk,
        d.name,
        d.date_creation.isoformat() if d.date_creation else None,
        d.date_modification.isoformat() if d.date_modification else None,
        d.date_publication.isoformat() if d.date_publication else None,
        Organisation.objects.get(id=d.organisation_id).name,
        d.editor.get_full_name() if d.editor != user else 'Moi',
        d.published,
        d.is_inspire,
        d.ckan_slug,
        ) for d in Dataset.get_subordinated_datasets(profile)]

    return render_with_info_profile(
        request, 'idgo_admin/all_datasets.html', status=200,
        context={'datasets': json.dumps(datasets),
                 'datasets_count': len(datasets)})


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def export(request, *args, **kwargs):
    from django.db.models import F
    user, profile = user_and_profile(request)

    if profile.get_roles()["is_referent"] and request.GET.get('mode') == 'all':
        datasets = Dataset.get_subordinated_datasets(profile)
    else:
        datasets = Dataset.objects.filter(editor=user)

    if request.GET.get('format') == 'csv':
        datasets = datasets.annotate(
            Auteur=F('editor__email'),
            Nom_organisation=F('organisation__name'),
            Titre_licence=F('license__title'),
            ).values(
                'name', 'description', 'Auteur', 'published', 'is_inspire',
                'date_creation', 'date_publication', 'date_modification',
                'Nom_organisation', 'Titre_licence', 'update_freq',
                'geocover', 'ckan_slug')
        return render_to_csv_response(datasets)

    raise Http404
