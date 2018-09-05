# Copyright (c) 2017-2018 Datasud.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanNotFoundError
from idgo_admin.ckan_module import CkanSyncingError
from idgo_admin.ckan_module import CkanTimeoutError
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.dataset import DatasetForm as Form
from idgo_admin.models import Category
from idgo_admin.models import Dataset
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import License
from idgo_admin.models import Mail
from idgo_admin.models import Organisation
from idgo_admin.models import Resource
from idgo_admin.models import ResourceFormats
from idgo_admin.models import Support
from idgo_admin.mra_client import MRANotFoundError
from idgo_admin.shortcuts import get_object_or_404_extended
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
from idgo_admin.views.resource import get_layers
import json


CKAN_URL = settings.CKAN_URL
READTHEDOC_URL = settings.READTHEDOC_URL

decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class DatasetManager(View):

    template = 'idgo_admin/dataset.html'
    namespace = 'idgo_admin:dataset'
    namespace_resource = 'idgo_admin:resource'

    def get_context(self, form, profile, dataset):

        resources = []
        ogc_layers = []
        for resource in Resource.objects.filter(dataset=dataset):
            resources.append((
                resource.pk,
                resource.name,
                resource.format_type.extension,
                resource.get_data_type_display(),
                resource.created_on.isoformat() if resource.created_on else None,
                resource.last_update.isoformat() if resource.last_update else None,
                resource.get_restricted_level_display(),
                str(resource.ckan_id),
                resource.datagis_id and [str(uuid) for uuid in resource.datagis_id] or [],
                resource.ogc_services,
                resource.extractable))

            if resource.datagis_id:
                common = [
                    resource.pk, resource.name, resource.get_data_type_display(),
                    resource.get_restricted_level_display(),
                    resource.geo_restriction, resource.extractable,
                    resource.ogc_services]
                try:
                    ogc_layers += [
                        common + list(l) for l in get_layers(resource)]
                except MRANotFoundError:
                    pass

        return {
            'dataset': dataset,
            'doc_url': READTHEDOC_URL,
            'form': form,
            'licenses': dict(
                (o.pk, o.license.pk) for o
                in LiaisonsContributeurs.get_contribs(profile=profile) if o.license),
            'ogc_layers': json.dumps(ogc_layers),
            'resources': json.dumps(resources),
            'supports': json.dumps(dict(
                (item.pk, {'name': item.name, 'email': item.email})
                for item in Support.objects.all())),
            'tags': json.dumps(ckan.get_tags())}

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)

        if not LiaisonsContributeurs.objects.filter(
                profile=profile, validated_on__isnull=False).exists():
            raise Http404

        _ckan_slug = request.GET.get('ckan_slug')
        if _ckan_slug:
            instance = get_object_or_404_extended(
                Dataset, user, include={'ckan_slug': _ckan_slug})
            return redirect(
                reverse(self.namespace) + '?id={0}'.format(instance.pk))

        id = request.POST.get('id', request.GET.get('id'))
        instance = id and get_object_or_404_extended(
            Dataset, user, include={'id': id}) or None

        form = Form(instance=instance, include={
            'user': user, 'id': id, 'identification': id and True or False})

        context = self.get_context(form, profile, instance)

        return render_with_info_profile(request, self.template, context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    @transaction.atomic
    def post(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)

        id = request.POST.get('id', request.GET.get('id'))
        instance = id and get_object_or_404_extended(
            Dataset, user, include={'id': id}) or None

        form = Form(
            request.POST, request.FILES, instance=instance, include={
                'user': user, 'id': id, 'identification': id and True or False})

        context = self.get_context(form, profile, instance)

        if not form.is_valid():
            errors = form._errors.get('__all__', [])
            errors and messages.error(request, ' '.join(errors))
            return render_with_info_profile(request, self.template, context)

        try:
            with transaction.atomic():
                instance = form.handle_me(request, id=id)
        except ValidationError as e:
            messages.error(request, ' '.join(e))
        except CkanSyncingError as e:
            form.add_error('__all__', e.__str__())
            messages.error(request, e.__str__())
        except CkanTimeoutError as e:
            form.add_error('__all__', e.__str__())
            messages.error(request, e.__str__())
        else:
            # if id:
            #     Mail.updating_a_dataset(profile, instance)
            # else:
            #     Mail.creating_a_dataset(profile, instance)

            messages.success(request, (
                'Le jeu de données a été {0} avec succès. Souhaitez-vous '
                '<a href="{1}">créer un nouveau jeu de données</a> ? ou '
                '<a href="{2}">ajouter une ressource</a> ? ou bien '
                '<a href="{3}/dataset/{4}" target="_blank">voir le jeu '
                'de données dans CKAN</a> ?').format(
                    id and 'mis à jour' or 'créé',
                    reverse(self.namespace),
                    reverse(self.namespace_resource,
                            kwargs={'dataset_id': instance.id}),
                    CKAN_URL,
                    instance.ckan_slug))

            if 'continue' in request.POST:
                return HttpResponseRedirect('{0}?id={1}'.format(
                    reverse(self.namespace), instance.id))

            namespace = instance.editor == profile.user and 'datasets' or 'all_datasets'
            return HttpResponseRedirect('{0}#datasets/{1}'.format(
                reverse('idgo_admin:{0}'.format(namespace)), instance.id))

        return render_with_info_profile(request, self.template, context)

    @ExceptionsHandler(ignore=[Http404, CkanSyncingError],
                       actions={ProfileHttp404: on_profile_http404})
    def delete(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)

        id = request.POST.get('id', request.GET.get('id'))
        if not id:
            raise Http404

        instance = get_object_or_404_extended(
            Dataset, user, include={'id': id})

        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])
        try:
            ckan_user.delete_dataset(instance.ckan_slug)  # purge réalisé au delete()
        except CkanNotFoundError as e:
            status = 500
            messages.error(request, e.__str__())
        except CkanSyncingError as e:
            status = 500
            messages.error(request, e.__str__())
        else:
            instance.delete()
            # Mail.deleting_a_dataset(profile, instance)

            status = 200
            message = 'Le jeu de données a été supprimé avec succès.'
            messages.success(request, message)
        finally:
            ckan_user.close()

        return HttpResponse(status=status)


def get_all_organisations(profile, strict=False):
    role = profile.get_roles()

    if role['is_admin'] and not strict:
        filters = {}
    elif role['is_referent'] and not strict:
        filters = {
            'liaisonsreferents__profile': profile,
            'liaisonsreferents__validated_on__isnull': False}
    else:
        filters = {
            'liaisonscontributeurs__profile': profile,
            'liaisonscontributeurs__validated_on__isnull': False}

    return [{
        'id': instance.ckan_slug,
        'name': instance.name
        } for instance in Organisation.objects.filter(is_active=True, **filters)]


def get_all_datasets(profile, strict=False):
    role = profile.get_roles()

    if role['is_admin'] and not strict:
        filters = {}
    elif role['is_referent'] and not strict:
        filters = {
            'organisation__in': LiaisonsReferents.get_subordinated_organizations(profile=profile)}
    else:
        filters = {'editor': profile.user}

    return [{
        'id': instance.ckan_slug,
        'name': instance.name
        } for instance in Dataset.objects.filter(**filters)]


def get_datasets(profile, qs, strict=False):

    filters = {}
    if strict:
        filters['editor'] = profile.user
    else:
        filters['organisation__in'] = \
            LiaisonsReferents.get_subordinated_organizations(profile=profile)

    q = qs.get('q', None)
    if q:
        filters['name__icontains'] = q
        filters['description__icontains'] = q

    private = {'true': True, 'false': False}.get(qs.get('private', '').lower())
    if private:
        filters['published'] = not private

    category = qs.get('category', None)
    if category:
        filters['categories__in'] = Category.objects.filter(ckan_slug=category)

    license = qs.get('license', None)
    if license:
        filters['license__id'] = license

    synchronisation = {'true': True, 'false': False}.get(qs.get('sync', '').lower())
    if synchronisation:
        filters['resource__synchronisation'] = synchronisation

    sync_frequency = qs.get('syncfrequency', None)
    if synchronisation and sync_frequency:
        filters['resource__sync_frequency'] = sync_frequency

    resource_format = qs.get('resourceformat', None)
    if resource_format:
        filters['resource__format_type__extension'] = resource_format

    return Dataset.objects.filter(**filters)


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def my_datasets(request, *args, **kwargs):

    user, profile = user_and_profile(request)

    all_categories = [
        {'id': instance.ckan_slug, 'name': instance.name}
        for instance in Category.objects.all()]
    all_datasets = get_all_datasets(profile, strict=True)
    all_licenses = [
        {'id': instance.id, 'name': instance.title}
        for instance in License.objects.all()]
    all_organisations = get_all_organisations(profile, strict=True)
    all_resourceformats = [
        {'id': instance.extension, 'name': instance.extension}
        for instance in ResourceFormats.objects.all()]
    all_update_frequencies = [
        {'id': choice[0], 'name': choice[1]}
        for choice in Resource.FREQUENCY_CHOICES]

    filtered_datasets = [(
        instance.pk,
        instance.name,
        instance.date_creation.isoformat() if instance.date_creation else None,
        instance.date_modification.isoformat() if instance.date_modification else None,
        instance.date_publication.isoformat() if instance.date_publication else None,
        Organisation.objects.get(id=instance.organisation_id).name,
        instance.editor.get_full_name() if instance.editor != profile.user else 'Moi',
        instance.published,
        instance.is_inspire,
        instance.ckan_slug,
        profile in LiaisonsContributeurs.get_contributors(instance.organisation)
        ) for instance in get_datasets(profile, request.GET, strict=True)]

    return render_with_info_profile(
        request, 'idgo_admin/datasets.html', status=200,
        context={
            'all_categories': all_categories,
            'all_datasets': all_datasets,
            'all_licenses': all_licenses,
            'all_organisations': all_organisations,
            'all_resourceformats': all_resourceformats,
            'all_update_frequencies': all_update_frequencies,
            'datasets': json.dumps(filtered_datasets),
            'datasets_count': len(filtered_datasets)})


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def all_datasets(request, *args, **kwargs):

    user, profile = user_and_profile(request)

    roles = profile.get_roles()
    if not roles['is_referent'] and not roles['is_admin']:
        raise Http404

    all_categories = [
        {'id': instance.ckan_slug, 'name': instance.name}
        for instance in Category.objects.all()]
    all_datasets = get_all_datasets(profile)
    all_licenses = [
        {'id': instance.id, 'name': instance.title}
        for instance in License.objects.all()]
    all_organisations = get_all_organisations(profile)
    all_resourceformats = [
        {'id': instance.extension, 'name': instance.extension}
        for instance in ResourceFormats.objects.all()]
    all_update_frequencies = [
        {'id': choice[0], 'name': choice[1]}
        for choice in Resource.FREQUENCY_CHOICES]

    filtered_datasets = [(
        instance.pk,
        instance.name,
        instance.date_creation.isoformat() if instance.date_creation else None,
        instance.date_modification.isoformat() if instance.date_modification else None,
        instance.date_publication.isoformat() if instance.date_publication else None,
        Organisation.objects.get(id=instance.organisation_id).name,
        instance.editor.get_full_name() if instance.editor != profile.user else 'Moi',
        instance.published,
        instance.is_inspire,
        instance.ckan_slug,
        profile in LiaisonsContributeurs.get_contributors(instance.organisation)
        ) for instance in get_datasets(profile, request.GET)]

    return render_with_info_profile(
        request, 'idgo_admin/all_datasets.html', status=200,
        context={
            'all_categories': all_categories,
            'all_datasets': all_datasets,
            'all_licenses': all_licenses,
            'all_organisations': all_organisations,
            'all_resourceformats': all_resourceformats,
            'all_update_frequencies': all_update_frequencies,
            'datasets': json.dumps(filtered_datasets),
            'datasets_count': len(filtered_datasets)})
