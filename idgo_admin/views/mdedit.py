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
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.geonet_module import GeonetUserHandler as geonet
from idgo_admin.models import Category
from idgo_admin.models import Dataset
from idgo_admin.models import MDEDIT_LOCALES
from idgo_admin.models import Organisation
from idgo_admin.models import Resource
from idgo_admin.shortcuts import get_object_or_404
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
from idgo_admin.utils import clean_my_obj
from idgo_admin.utils import open_json_staticfile
import os
import re
from urllib.parse import urljoin
from uuid import UUID
import xml.etree.ElementTree as ET


STATIC_URL = settings.STATIC_URL
GEONETWORK_URL = settings.GEONETWORK_URL
CKAN_URL = settings.CKAN_URL
DOMAIN_NAME = settings.DOMAIN_NAME
READTHEDOC_URL_INSPIRE = settings.READTHEDOC_URL_INSPIRE

MDEDIT_HTML_PATH = 'mdedit/html/'
MDEDIT_CONFIG_PATH = 'mdedit/config/'
MDEDIT_DATASET_MODEL = 'models/model-dataset-empty.json'
MDEDIT_SERVICE_MODEL = 'models/model-service-empty.json'


def join_url(filename, path=MDEDIT_CONFIG_PATH):
    return urljoin(urljoin(STATIC_URL, path), filename)


def prefill_dataset_model(dataset):

    model = open_json_staticfile(
        os.path.join(MDEDIT_CONFIG_PATH, MDEDIT_DATASET_MODEL))

    data = model.copy()
    editor = dataset.editor
    organisation = dataset.organisation

    default_contact = {
        'individualName': editor.get_full_name(),
        'organisationName': organisation.name,
        'email': organisation.email,
        'phoneVoice': organisation.phone,
        'deliveryPoint': organisation.address,
        'postalCode': organisation.postcode,
        'city': organisation.city}

    md_contacts = {**default_contact, **{'role': 'author'}}
    md_data_point_of_contacts = {**default_contact, **{'role': 'owner'}}

    try:
        organisation_logo = {
            'logoDescription': 'logo',
            'logoUrl': urljoin(DOMAIN_NAME, organisation.logo.url)}
    except Exception:
        pass
    else:
        md_contacts.update(organisation_logo)
        md_data_point_of_contacts.update(organisation_logo)

    data['mdContacts'].insert(0, md_contacts)
    data['dataPointOfContacts'].insert(0, md_data_point_of_contacts)

    data['dataTitle'] = dataset.name
    data['dataAbstract'] = dataset.description

    if dataset.date_creation:
        data['dataDates'].insert(0, {
            'date': dataset.date_creation.isoformat(),
            'dateType': 'creation'})
    if dataset.date_publication:
        data['dataDates'].insert(1, {
            'date': dataset.date_publication.isoformat(),
            'dateType': 'publication'})
    if dataset.date_modification:
        data['dataDates'].insert(2, {
            'date': dataset.date_modification.isoformat(),
            'dateType': 'revision'})

    data['dataMaintenanceFrequency'] = {
        'never': 'notPlanned',          # [011] There are no plans to update the data
        'asneeded': 'asNeeded',         # [009] Data is updated as deemed necessary
        'intermittently': 'irregular',  # [010] Data is updated in intervals that are uneven in duration
        'continuously': 'continual',    # [001] Data is repeatedly and frequently updated
        'realtime': 'continual',        # ??? -> [001]
        'daily': 'daily',               # [002] Data is updated each day
        'weekly': 'weekly',             # [003] data is updated on a weekly basis
        'fortnightly': 'fortnightly',   # [004] data is updated every two weeks
        'monthly': 'monthly',           # [005] data is updated each month
        'quarterly': 'quaterly',        # [006] data is updated every three months
        'semiannual': 'biannually',     # [007] data is updated twice each year
        'annual': 'annually'            # [008] data is updated every year
        }.get(dataset.update_freq, 'unknow')  # [012] frequency of maintenance for the data is not known

    if dataset.keywords:
        data['dataKeywords'].insert(0, {
            'keywords': [kw for kw in dataset.keywords.names()],
            'keywordType': 'theme'})

    for category in Category.objects.filter(dataset=dataset):
        iso_topic = category.iso_topic
        if iso_topic:
            data['dataTopicCategories'].append(iso_topic)

    try:
        data['dataBrowseGraphics'].insert(0, {
            'fileName': urljoin(DOMAIN_NAME, dataset.thumbnail.url),
            # 'fileDescription': 'Imagette',
            'fileType': dataset.thumbnail.name.split('.')[-1]})
    except Exception:
        pass

    resources = Resource.objects.filter(dataset=dataset)
    for resource in resources:
        entry = {
            'name': resource.name,
            'url': '{0}/dataset/{1}/resource/{2}'.format(
                CKAN_URL, dataset.ckan_slug, resource.ckan_id),
            'description': resource.description}
        protocol = resource.format_type.protocol
        if protocol:
            entry['protocol'] = protocol
        data['dataLinkages'].insert(0, entry)

    return clean_my_obj(data)


def prefill_service_model(organisation):

    model = open_json_staticfile(
        os.path.join(MDEDIT_CONFIG_PATH, MDEDIT_SERVICE_MODEL))

    data = model.copy()
    editor = None  # qui est l'éditeur ?

    default_contact = {
        # 'individualName': editor.get_full_name(),
        'organisationName': organisation.name,
        'email': organisation.email,
        'phoneVoice': organisation.phone,
        'deliveryPoint': organisation.address,
        'postalCode': organisation.postcode,
        'city': organisation.city}

    md_contacts = {**default_contact, **{'role': 'author'}}
    md_data_point_of_contacts = {**default_contact, **{'role': 'owner'}}

    try:
        logo = {
            'logoDescription': 'logo',
            'logoUrl': urljoin(DOMAIN_NAME, organisation.logo.url)}
    except Exception:
        pass
    else:
        md_contacts.update(logo)
        md_data_point_of_contacts.update(logo)

    data['mdContacts'].insert(0, md_contacts)
    data['dataPointOfContacts'].insert(0, md_data_point_of_contacts)

    return clean_my_obj(data)


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class DatasetMDEditTplEdit(View):

    template = 'idgo_admin/mdedit/template_dataset_edit.html'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id, *args, **kwargs):
        user, profile = user_and_profile(request)
        get_object_or_404(Dataset, id=id)
        return render(request, self.template)


@method_decorator(decorators, name='dispatch')
class DatasetMDEdit(View):

    template = 'idgo_admin/mdedit/dataset.html'
    namespace = 'idgo_admin:dataset_mdedit'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id, *args, **kwargs):
        user, profile = user_and_profile(request)
        instance = get_object_or_404(Dataset, id=id)

        config = {
            'app_name': 'mdEdit',
            'app_title': 'mdEdit',
            'app_version': '0.14.9',
            'app_copyrights': '(c) CIGAL 2016',
            'languages': {'locales': ['fr']},
            'defaultLanguage': 'fr',
            'server_url_md': GEONETWORK_URL,
            'views': {
                'list': [{
                    # 'path': '{id}/edit/'.format(id=id),
                    'path': reverse('idgo_admin:dataset_mdedit_tpl_edit', kwargs={'id': instance.id}),
                    'values': {'fr': 'Edition'},
                    'locales': {'fr': join_url('views/edit/tpl-edit_fr.json')}
                    }, {
                    'path': join_url('tpl-view.html', path=MDEDIT_HTML_PATH),
                    'values': {'fr': 'Vue'},
                    'locales': {'fr': join_url('views/view/tpl-view_fr.json')}
                    }]},
            'models': {
                'list': [{
                    'path': join_url(MDEDIT_DATASET_MODEL),
                    'value': 'Modèle de fiche vierge'
                    }]},
            'locales': MDEDIT_LOCALES,
            'locales_path': join_url('locales/'),
            'geographicextents_list': join_url('list_geographicextents.json'),
            'referencesystems_list': join_url('list_referencesystems.json'),
            'static_root': join_url('libs/mdedit/', path=STATIC_URL),
            'modal_template': {
                'help': join_url('modal-help.html', path=MDEDIT_HTML_PATH)}}

        context = {'dataset': instance,
                   'doc_url': READTHEDOC_URL_INSPIRE,
                   'config': config}

        record = instance.geonet_id and geonet.get_record(str(instance.geonet_id)) or None

        if record:
            xml = record.xml.decode(encoding='utf-8')
            context['record_xml'] = re.sub('\n', '', xml).replace("'", "\\'")  # C'est moche
        else:
            context['record_obj'] = prefill_dataset_model(instance)

        return render_with_info_profile(request, self.template, context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, id, *args, **kwargs):

        user, profile = user_and_profile(request)

        dataset = get_object_or_404(Dataset, id=id)

        if not request.is_ajax():
            return HttpResponseRedirect(
                reverse(self.namespace, kwargs={'dataset_id': id}))

        root = ET.fromstring(request.body)
        ns = {'gmd': 'http://www.isotc211.org/2005/gmd',
              'gco': 'http://www.isotc211.org/2005/gco'}
        id = root.find('gmd:fileIdentifier/gco:CharacterString', ns).text

        record = ET.tostring(
            root, encoding='utf-8', method='xml', short_empty_elements=True)

        # Ça marche mais c'est moche et illisible...
        # TODO: faire du code plus beau ; gérer les exceptions mieux que ça.
        if not geonet.get_record(id):
            try:
                geonet.create_record(id, record)
            except Exception:
                messages.error(request, 'La création de la fiche de métadonnées a échoué.')
            else:
                geonet.publish(id)  # Toujours publier la fiche
                dataset.geonet_id = UUID(id)
                dataset.save(current_user=None)
                messages.success(
                    request, 'La fiche de metadonnées a été créée avec succès.')
        else:
            try:
                geonet.update_record(id, record)
            except Exception:
                messages.error(request, 'La mise à jour de la fiche de métadonnées a échoué.')
            else:
                messages.success(
                    request, 'La fiche de metadonnées a été créée avec succès.')

        return HttpResponse()


@method_decorator(decorators, name='dispatch')
class ServiceMDEditTplEdit(View):

    template = 'idgo_admin/mdedit/template_service_edit.html'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id, *args, **kwargs):
        user, profile = user_and_profile(request)
        get_object_or_404(Organisation, id=id, is_active=True)
        return render(request, self.template)


@method_decorator(decorators, name='dispatch')
class ServiceMDEdit(View):

    template = 'idgo_admin/mdedit/service.html'
    namespace = 'idgo_admin:service_mdedit'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id, *args, **kwargs):
        user, profile = user_and_profile(request)
        instance = get_object_or_404(Organisation, id=id, is_active=True)

        config = {
            'app_name': 'mdEdit',
            'app_title': 'mdEdit',
            'app_version': '0.14.9',
            'app_copyrights': '(c) CIGAL 2016',
            'languages': {'locales': ['fr']},
            'defaultLanguage': 'fr',
            'server_url_md': GEONETWORK_URL,
            'views': {
                'list': [{
                    'path': reverse('idgo_admin:service_mdedit_tpl_edit', kwargs={'id': instance.id}),
                    'values': {'fr': 'Edition'},
                    'locales': {'fr': join_url('views/edit/tpl-edit_fr.json')}
                    }, {
                    'path': join_url('tpl-view.html', path=MDEDIT_HTML_PATH),
                    'values': {'fr': 'Vue'},
                    'locales': {'fr': join_url('views/view/tpl-view_fr.json')}
                    }]},
            'models': {
                'list': [{
                    'path': join_url(MDEDIT_SERVICE_MODEL),
                    'value': 'Modèle de fiche vierge'
                    }]},
            'locales': MDEDIT_LOCALES,
            'locales_path': join_url('locales/'),
            'geographicextents_list': join_url('list_geographicextents.json'),
            'referencesystems_list': join_url('list_referencesystems.json'),
            'static_root': join_url('libs/mdedit/', path=STATIC_URL),
            'modal_template': {
                'help': join_url('modal-help.html', path=MDEDIT_HTML_PATH)}}

        context = {'organisation': instance,
                   'doc_url': READTHEDOC_URL_INSPIRE,
                   'config': config}

        record = instance.geonet_id and geonet.get_record(str(instance.geonet_id)) or None

        if record:
            xml = record.xml.decode(encoding='utf-8')
            context['record_xml'] = re.sub('\n', '', xml).replace("'", "\\'")  # C'est moche
        else:
            context['record_obj'] = prefill_service_model(instance)

        return render_with_info_profile(request, self.template, context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, id, *args, **kwargs):

        user, profile = user_and_profile(request)

        instance = get_object_or_404(Organisation, id=id, is_active=True)

        if not request.is_ajax():
            return HttpResponseRedirect(
                reverse(self.namespace, kwargs={'id': instance.id}))

        root = ET.fromstring(request.body)
        ns = {'gmd': 'http://www.isotc211.org/2005/gmd',
              'gco': 'http://www.isotc211.org/2005/gco'}
        id = root.find('gmd:fileIdentifier/gco:CharacterString', ns).text

        record = ET.tostring(
            root, encoding='utf-8', method='xml', short_empty_elements=True)

        if not geonet.is_record_exists(id):
            try:
                geonet.create_record(id, record)
            except Exception:
                messages.error(request, 'La création de la fiche de métadonnées a échoué.')
            else:
                geonet.publish(id)  # Toujours publier la fiche
                instance.geonet_id = UUID(id)
                instance.save()
                messages.success(
                    request, 'La fiche de metadonnées a été créée avec succès.')
        else:
            try:
                geonet.update_record(id, record)
            except Exception:
                messages.error(request, 'La mise à jour de la fiche de métadonnées a échoué.')
            else:
                messages.success(
                    request, 'La fiche de metadonnées a été créée avec succès.')

        return HttpResponse()


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def mdhandler(request, type, *args, **kwargs):
    user, profile = user_and_profile(request)

    if type == 'dataset':
        target = Dataset
        namespace = 'idgo_admin:dataset_mdedit'
    elif type == 'service':
        target = Organisation
        namespace = 'idgo_admin:service_mdedit'

    instance = get_object_or_404(target, id=request.GET.get('id'))
    return redirect(reverse(namespace, kwargs={'id': instance.id}))
