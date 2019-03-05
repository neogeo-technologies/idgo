# Copyright (c) 2017-2019 Datasud.
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
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.dataset import DatasetForm as Form
from idgo_admin.models import Category
from idgo_admin.models import Dataset
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import License
from idgo_admin.models.mail import send_dataset_creation_mail
from idgo_admin.models.mail import send_dataset_delete_mail
from idgo_admin.models.mail import send_dataset_update_mail
from idgo_admin.models import Organisation
from idgo_admin.models import Resource
from idgo_admin.models import ResourceFormats
from idgo_admin.models import Support
from idgo_admin.mra_client import MRANotFoundError
from idgo_admin.shortcuts import get_object_or_404_extended
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
from idgo_admin.views.layer import get_layers
import json
from math import ceil


CKAN_URL = settings.CKAN_URL

decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def dataset(request, *args, **kwargs):

    user, profile = user_and_profile(request)

    id = request.GET.get('id', request.GET.get('slug'))
    if not id:
        raise Http404

    kvp = {}
    try:
        id = int(id)
    except ValueError:
        kvp['slug'] = id
    else:
        kvp['id'] = id
    finally:
        instance = get_object_or_404(Dataset, **kvp)

    # Redirect to layer
    return redirect(reverse('idgo_admin:dataset_editor', kwargs={'id': instance.id}))


@method_decorator(decorators, name='dispatch')
class DatasetManager(View):

    def get_context(self, form, profile, dataset):

        resources = []
        ogc_layers = []
        for resource in Resource.objects.filter(dataset=dataset):
            resources.append((
                resource.pk,
                resource.title,
                resource.format_type.description,
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
                    resource.pk, resource.title, resource.get_data_type_display(),
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
            'form': form,
            'licenses': dict(
                (o.pk, o.license.pk) for o
                in LiaisonsContributeurs.get_contribs(profile=profile) if o.license),
            'ogc_layers': json.dumps(ogc_layers),
            'resources': json.dumps(resources),
            'supports': json.dumps(dict(
                (item.pk, {'name': item.name, 'email': item.email})
                for item in Support.objects.all())),
            'tags': json.dumps(CkanHandler.get_tags())}

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id, *args, **kwargs):
        user, profile = user_and_profile(request)

        if not LiaisonsContributeurs.objects.filter(
                profile=profile, validated_on__isnull=False).exists():
            raise Http404

        instance = None
        if id != 'new':
            instance = get_object_or_404_extended(Dataset, user, include={'id': id})
        else:
            id = None

        form = Form(instance=instance, include={
            'user': user, 'id': id, 'identification': id and True or False})

        context = self.get_context(form, profile, instance)

        return render_with_info_profile(request, 'idgo_admin/dataset/dataset.html', context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    @transaction.atomic
    def post(self, request, id, *args, **kwargs):

        user, profile = user_and_profile(request)

        if not LiaisonsContributeurs.objects.filter(
                profile=profile, validated_on__isnull=False).exists():
            raise Http404

        instance = None
        if id != 'new':
            instance = get_object_or_404_extended(Dataset, user, include={'id': id})
        else:
            id = None

        form = Form(
            request.POST, request.FILES, instance=instance, include={
                'user': user, 'id': id, 'identification': id and True or False})

        context = self.get_context(form, profile, instance)

        if not form.is_valid():
            errors = form._errors.get('__all__', [])
            errors and messages.error(request, ' '.join(errors))
            return render_with_info_profile(request, 'idgo_admin/dataset/dataset.html', context)

        data = form.cleaned_data

        kvp = {
            'broadcaster_name': data['broadcaster_name'],
            'broadcaster_email': data['broadcaster_email'],
            'slug': data['slug'],
            'date_creation': data['date_creation'],
            'date_modification': data['date_modification'],
            'date_publication': data['date_publication'],
            'description': data['description'],
            'geocover': data['geocover'],
            'granularity': data['granularity'],
            'license': data['license'],
            'title': data['title'],
            'organisation': data['organisation'],
            'owner_email': data['owner_email'],
            'owner_name': data['owner_name'],
            'update_frequency': data['update_frequency'],
            'published': data['published'],
            'support': data['support'],
            'thumbnail': data['thumbnail'],
            'is_inspire': data['is_inspire']}

        try:
            with transaction.atomic():
                if id:
                    instance = Dataset.objects.get(pk=id)
                    for k, v in kvp.items():
                        setattr(instance, k, v)
                else:
                    kvp['editor'] = user
                    save_opts = {'current_user': user, 'synchronize': False}
                    instance = Dataset.default.create(save_opts=save_opts, **kvp)

                instance.categories.set(data.get('categories', []), clear=True)
                keywords = data.get('keywords')
                if keywords:
                    instance.keywords.clear()
                    for k in keywords:
                        instance.keywords.add(k)
                instance.data_type.set(data.get('data_type', []), clear=True)
                instance.save(current_user=user, synchronize=True)

        except ValidationError as e:
            messages.error(request, ' '.join(e))
        except CkanBaseError as e:
            form.add_error('__all__', e.__str__())
            messages.error(request, e.__str__())
        else:
            if id:
                send_dataset_update_mail(user, instance)
            else:
                send_dataset_creation_mail(user, instance)

            if id:
                messages.success(request, 'Le jeu de données a été mis à jour avec succès.')
            else:
                messages.success(request, (
                    'Le jeu de données a été créé avec succès. Souhaitez-vous '
                    '<a href="{0}">créer un nouveau jeu de données</a> ? ou '
                    '<a href="{1}">ajouter une ressource</a> ? ou bien '
                    '<a href="{2}/dataset/{3}" target="_blank">voir le jeu '
                    'de données dans CKAN</a> ?').format(
                        reverse('idgo_admin:dataset_editor', kwargs={'id': 'new'}),
                        reverse('idgo_admin:resource', kwargs={'dataset_id': instance.id}),
                        CKAN_URL, instance.slug))

            if 'continue' in request.POST:
                return HttpResponseRedirect(
                    reverse('idgo_admin:dataset_editor', kwargs={'id': instance.id}))

            target = instance.editor == profile.user and 'mine' or 'all'
            return HttpResponseRedirect('{0}#{1}'.format(
                reverse('idgo_admin:datasets', kwargs={'target': target}),
                instance.slug))

        return render_with_info_profile(request, 'idgo_admin/dataset/dataset.html', context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def delete(self, request, id, *args, **kwargs):

        if id == 'new':
            raise Http404

        user, profile = user_and_profile(request)

        if not LiaisonsContributeurs.objects.filter(
                profile=profile, validated_on__isnull=False).exists():
            raise Http404

        dataset = get_object_or_404_extended(Dataset, user, include={'id': id})

        try:
            dataset.delete(current_user=user)
        except Exception as e:
            status = 500
            message = e.__str__()
            messages.error(request, message)
        else:
            status = 200
            message = 'Le jeu de données a été supprimé avec succès.'
            messages.success(request, message)

            send_dataset_delete_mail(user, dataset)

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
        'id': instance.slug,
        'legal_name': instance.legal_name
        } for instance in Organisation.objects.filter(is_active=True, **filters)]


def get_all_datasets(profile, strict=False, harvested=False):
    role = profile.get_roles()
    if harvested:
        strict = False
    if role['is_admin'] and not strict:
        # L'administrateur accède à tous les jeux de données.
        filters = {}
    elif role['is_referent'] and not strict:
        # Le référent accède au jeux de données des organisations
        # pour lesquelles il est référent.
        filters = {
            'organisation__in': LiaisonsReferents.get_subordinated_organisations(profile=profile)}
    else:
        # Un utilisateur classique ne voit que ses jeux de données
        filters = {'editor': profile.user}

    return [{
        'id': instance.slug,
        'title': instance.title
        } for instance in Dataset.objects.filter(**filters)]


def get_datasets(profile, qs, strict=False, harvested=False):
    filters = {}

    if harvested:
        D_ = Dataset.harvested
        # Si `harvested` est True, `strict` est tjs False
        strict = False
    else:
        D_ = Dataset.objects.exclude(
            pk__in=[x.pk for x in Dataset.harvested.all()])

    if strict:
        filters['editor'] = profile.user
    else:
        filters['organisation__in'] = \
            LiaisonsReferents.get_subordinated_organisations(profile=profile)

    organisation = qs.get('organisation', None)
    if organisation:
        filters['organisation__in'] = Organisation.objects.filter(slug=organisation)

    q = qs.get('q', None)
    if q:
        filters['title__icontains'] = q
        # filters['description__icontains'] = q

    private = {'true': True, 'false': False}.get(qs.get('private', '').lower())
    if private:
        filters['published'] = not private

    category = qs.get('category', None)
    if category:
        filters['categories__in'] = Category.objects.filter(slug=category)

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
        filters['resource__format_type__slug'] = resource_format

    return D_.filter(**filters)


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def datasets(request, target, *args, **kwargs):

    user, profile = user_and_profile(request)

    all = target == 'all'
    harvested = target == 'harvested'
    if all or harvested:
        # Réservé aux référents ou administrateurs IDGO
        roles = profile.get_roles()
        if not roles['is_referent'] and not roles['is_admin']:
            raise Http404

    all_categories = [
        {'id': instance.slug, 'name': instance.name}
        for instance in Category.objects.all()]
    all_datasets = get_all_datasets(profile, strict=not all, harvested=harvested)
    all_licenses = [
        {'id': instance.pk, 'name': instance.title}
        for instance in License.objects.all()]
    all_organisations = get_all_organisations(profile)
    all_resourceformats = [
        {'id': instance.slug, 'name': instance.description}
        for instance in ResourceFormats.objects.all()]
    all_update_frequencies = [
        {'id': choice[0], 'name': choice[1]}
        for choice in Resource.FREQUENCY_CHOICES]

    datasets = get_datasets(
        profile, request.GET, strict=not all, harvested=harvested)

    # Gestion du tri
    order_by = request.GET.get('sortby', None)
    if order_by:
        if order_by.endswith('organisation'):
            # Trier par le nom de l'organisation
            order_by = '{}__slug'.format(order_by)
        if order_by.endswith('editor'):
            # Trier par le nom de famille de l'utilisateur
            order_by = '{}__last_name'.format(order_by)
        order_by = {
            '-private': 'published',
            'private': '-published'}.get(order_by, order_by)

        datasets = datasets.order_by(order_by)

    # Gestion de la pagination
    page_number = int(request.GET.get('page', 1))
    items_per_page = int(request.GET.get('count', 10))
    number_of_pages = ceil(len(datasets) / items_per_page)
    if number_of_pages < page_number:
        page_number = 1
    x = items_per_page * page_number - items_per_page
    y = x + items_per_page

    return render_with_info_profile(
        request, 'idgo_admin/dataset/datasets.html', status=200,
        context={
            'all': all,
            'all_categories': all_categories,
            'all_datasets': all_datasets,
            'all_licenses': all_licenses,
            'all_organisations': all_organisations,
            'all_resourceformats': all_resourceformats,
            'all_update_frequencies': all_update_frequencies,
            'datasets': datasets[x:y],
            'harvested': harvested,
            'pagination': {
                'current': page_number,
                'total': number_of_pages},
            'total': len(datasets)})
