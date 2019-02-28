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


from collections import OrderedDict
# from django.conf import settings
# from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.api.utils import BasicAuth
from idgo_admin.api.utils import parse_request
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.exceptions import GenericException
from idgo_admin.forms.dataset import DatasetForm as Form
from idgo_admin.models import Dataset
from idgo_admin.models import License
from idgo_admin.models.mail import send_dataset_creation_mail
from idgo_admin.models.mail import send_dataset_delete_mail
from idgo_admin.models.mail import send_dataset_update_mail
from idgo_admin.models import Organisation
from idgo_admin.utils import slugify


def serialize(dataset):

    if dataset.keywords:
        keywords = [
            keyword.name for keyword in dataset.keywords.all()]
    else:
        keywords = None

    if dataset.categories:
        categories = [
            category.ckan_slug for category in dataset.categories.all()]
    else:
        categories = None

    if dataset.organisation:
        organisation = dataset.organisation.ckan_slug
    else:
        organisation = None

    if dataset.license:
        license = dataset.license.slug
    else:
        license = None

    if dataset.data_type:
        data_type = [
            data_type.ckan_slug for data_type in dataset.data_type.all()]
    else:
        data_type = None

    if dataset.granularity:
        granularity = dataset.granularity.slug
    else:
        granularity = None

    if dataset.bbox:
        minx, miny, maxx, maxy = dataset.bbox.extent
        extent = [[miny, minx], [maxy, maxx]]
    else:
        extent = None

    return OrderedDict([
        ('name', dataset.ckan_slug),
        ('title', dataset.name),
        ('description', dataset.description),
        ('keywords', keywords),
        ('categories', categories),
        ('date_creation', dataset.date_creation),
        ('date_modification', dataset.date_modification),
        ('date_publication', dataset.date_publication),
        ('update_frequency', dataset.date_publication),
        ('geocover', dataset.geocover),
        ('organisation', organisation),
        ('license', license),
        ('type', data_type),
        ('published', dataset.published),
        ('owner_name', dataset.owner_name),
        ('owner_email', dataset.owner_name),
        ('broadcaster_name', dataset.broadcaster_name),
        ('broadcaster_email', dataset.broadcaster_name),
        ('granularity', granularity),
        ('extent', extent),
        ])


def handler_get_request(request):
    user = request.user
    if user.profile.is_admin:
        datasets = Dataset.objects.all()
    else:
        s1 = set(Dataset.objects.filter(organisation__in=user.profile.referent_for))
        s2 = set(Dataset.objects.filter(editor=user))
        datasets = list(s1 | s2)
    return datasets


def handle_pust_request(request, dataset_name=None):
    # title -> name
    # name -> ckan_slug
    # description -> description
    # thumbnail -> {File}
    # keywords ->
    # categories ->
    # date_creation -> date_creation
    # date_modification -> date_modification
    # update_frequency -> update_freq
    # granularity -> granularity
    # organisation -> organisation.ckan_slug
    # license -> license.pk
    # support -> support
    # data_type -> type
    # owner_name -> owner_name
    # owner_email -> owner_email
    # broadcaster_name -> broadcaster_name
    # broadcaster_email -> broadcaster_email
    # published -> private
    user = request.user
    dataset = None
    if dataset_name:
        for instance in handler_get_request(request):
            if dataset.ckan_slug == dataset_name:
                dataset = instance
                break
        if not instance:
            raise Http404()

    # TODO: Vérifier les droits

    data = getattr(request, request.method).dict()

    try:
        organisation = Organisation.objects.get(ckan_slug=data.get('organisation'))
        license = License.objects.get(slug=data.get('license'))
    except (Organisation.DoesNotExist, License.DoesNotExist) as e:
        raise GenericException(details=e.__str__())

    data_form = {
        'name': data.get('title'),
        'ckan_slug': data.get('name', slugify(data.get('title'))),
        'description': data.get('description'),
        # 'thumbnail' -> request.FILES
        'keywords': data.get('keywords'),
        'categories': data.get('categories'),
        'date_creation': data.get('date_creation'),
        'date_modification': data.get('date_modification'),
        'date_publication': data.get('date_publication'),
        'update_freq': data.get('update_frequency'),
        # 'geocover'
        'granularity': data.get('granularity', 'indefinie'),
        'organisation': organisation.pk,
        'license': license.pk,
        'support': data.get('support', True),
        'data_type': data.get('type'),
        'owner_name': data.get('owner_name'),
        'owner_email': data.get('owner_email'),
        'broadcaster_name': data.get('broadcaster_name'),
        'broadcaster_email': data.get('broadcaster_email'),
        'published': not data.get('private', False),
        # 'is_inspire'
        }

    pk = dataset and dataset.pk or None
    include = {'user': user, 'id': pk, 'identification': pk and True or False}
    form = Form(data_form, request.FILES, instance=dataset, include=include)
    if not form.is_valid():
        raise GenericException(details=form._errors)

    data = form.cleaned_data
    kvp = {
        'name': data['name'],
        'ckan_slug': data['ckan_slug'],
        'description': data['description'],
        'thumbnail': data['thumbnail'],
        # keywords
        # categories
        'date_creation': data['date_creation'],
        'date_modification': data['date_modification'],
        'date_publication': data['date_publication'],
        'update_freq': data['update_freq'],
        'geocover': data['geocover'],
        'granularity': data['granularity'],
        'organisation': data['organisation'],
        'license': data['license'],
        'support': data['support'],
        # 'data_type': data['data_type'],
        'owner_email': data['owner_email'],
        'owner_name': data['owner_name'],
        'broadcaster_name': data['broadcaster_name'],
        'broadcaster_email': data['broadcaster_email'],
        'published': data['published'],
        # 'is_inspire': data['is_inspire'],
        }

    try:
        with transaction.atomic():
            if pk:
                dataset = Dataset.objects.get(pk=pk)
                for k, v in kvp.items():
                    setattr(instance, k, v)
            else:
                kvp['editor'] = user
                save_opts = {'current_user': user, 'synchronize': False}
                dataset = Dataset.default.create(save_opts=save_opts, **kvp)

            dataset.categories.set(data.get('categories', []), clear=True)
            keywords = data.get('keywords')
            if keywords:
                dataset.keywords.clear()
                for k in keywords:
                    dataset.keywords.add(k)
            dataset.data_type.set(data.get('data_type', []), clear=True)
            dataset.save(current_user=user, synchronize=True)
    except ValidationError as e:
        form.add_error('__all__', e.__str__())
    except CkanBaseError as e:
        form.add_error('__all__', e.__str__())
    else:
        if dataset_name:
            send_dataset_update_mail(user, dataset)
        else:
            send_dataset_creation_mail(user, dataset)
        return dataset
    raise GenericException(details=form.__str__())


# decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]
decorators = [csrf_exempt, BasicAuth()]


@method_decorator(decorators, name='dispatch')
class DatasetShow(View):

    def get(self, request, dataset_name):
        """Voir le jeu de données."""
        datasets = handler_get_request(request)
        for dataset in datasets:
            if dataset.ckan_slug == dataset_name:
                return JsonResponse(serialize(dataset), safe=True)
        raise Http404()

    def put(self, request, dataset_name):
        """Modifier le jeu de données."""
        # Django fait les choses à moitié...
        request.PUT, request._files = parse_request(request)
        try:
            handle_pust_request(request, dataset_name=dataset_name)
        except Http404:
            raise Http404()
        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)
        return HttpResponse(status=204)

    def delete(self, request, dataset_name):
        """Supprimer le jeu de données."""
        instance = None
        for dataset in handler_get_request(request):
            if dataset.ckan_slug == dataset_name:
                instance = dataset
                break
        if not instance:
            raise Http404()
        instance.delete(current_user=request.user)
        send_dataset_delete_mail(request.user, instance)
        return HttpResponse(status=204)


@method_decorator(decorators, name='dispatch')
class DatasetList(View):

    def get(self, request):
        """Voir les jeux de données."""
        datasets = handler_get_request(request)
        return JsonResponse(
            [serialize(dataset) for dataset in datasets], safe=False)

    def post(self, request):
        """Modifier le jeu de données."""
        try:
            handle_pust_request(request)
        except Http404:
            raise Http404()
        except GenericException as e:
            return JsonResponse({'error': e.details}, status=400)
        response = HttpResponse(status=201)
        response['Content-Location'] = ''
        return response