from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.dataset import publish_dataset_to_ckan
from idgo_admin.geonet_module import GeonetUserHandler as geonet
from idgo_admin.models import Category
from idgo_admin.models import Dataset
from idgo_admin.models import MDEDIT_LOCALES
from idgo_admin.models import Resource
from idgo_admin.shortcuts import get_object_or_404_extended
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
from idgo_admin.utils import clean_my_obj
from idgo_admin.utils import open_json_staticfile
from idgo_admin.utils import three_suspension_points
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


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


def prefill_model(model, dataset):

    data = model.copy()
    editor = dataset.editor
    organization = dataset.organisation

    data['mdContacts'].insert(0, {
        'role': 'author',
        'individualName': editor.get_full_name(),
        'organisationName': organization.name,
        'email': organization.email,
        'phoneVoice': organization.org_phone,
        'deliveryPoint': organization.address,
        'postalCode': organization.postcode,
        'city': dataset.organisation.city})

    data['dataPointOfContacts'].insert(0, {
        'role': 'owner',
        'individualNzame': editor.get_full_name(),
        'organisationName': organization.name,
        'email': organization.email,
        'phoneVoice': organization.org_phone,
        'deliveryPoint': organization.address,
        'postalCode': organization.postcode,
        'city': dataset.organisation.city})

    try:
        data['mdContacts'][0].update({
            'logoDescription': 'logo',
            'logoUrl': urljoin(DOMAIN_NAME, organization.logo.url)})
    except Exception:
        pass

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

    data['dataMaintenanceFrequency'] = dataset.update_freq or 'unknown'

    if dataset.keywords:
        data['dataKeywords'].insert(0, {
            'keywords': [kw for kw in dataset.keywords.names()],
            'keywordType': 'theme'})

    for category in Category.objects.filter(dataset=dataset):
        iso_topic = category.iso_topic
        if iso_topic:
            data['dataTopicCategories'].append(iso_topic)

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


@method_decorator(decorators, name='dispatch')
class MDEditTplEdit(View):

    template = 'idgo_admin/mdedit/template_edit.html'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, dataset_id, *args, **kwargs):

        def join_url(filename, path='mdedit/html/'):
            return urljoin(urljoin(STATIC_URL, path), filename)

        user, profile = user_and_profile(request)

        dataset = get_object_or_404_extended(
            Dataset, user, include={'id': dataset_id})
        del dataset

        return render(request, self.template)


@method_decorator(decorators, name='dispatch')
class MDEdit(View):

    template = 'idgo_admin/mdedit.html'
    namespace = 'idgo_admin:mdedit'
    config_path = 'mdedit/config/'
    html_path = 'mdedit/html/'
    locales = MDEDIT_LOCALES
    geonetwork_url = GEONETWORK_URL
    static_url = STATIC_URL

    # filenames
    model_json = 'models/model-empty.json'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, dataset_id, *args, **kwargs):

        user, profile = user_and_profile(request)

        dataset = get_object_or_404_extended(
            Dataset, user, include={'id': dataset_id})

        def join_url(filename, path=self.config_path):
            return urljoin(urljoin(self.static_url, path), filename)

        def server_url(namespace):
            return reverse('idgo_admin:{0}'.format(namespace),
                           kwargs={'dataset_id': dataset.id})

        config = {
            'app_name': 'mdEdit',
            'app_title': 'mdEdit',
            'app_version': '0.14.9',
            'app_copyrights': '(c) CIGAL 2016',
            'languages': {'locales': ['fr']},
            'defaultLanguage': 'fr',
            'server_url_md': self.geonetwork_url,
            'views': {
                'list': [{
                    'path': 'mdedit/edit/',
                    'values': {'fr': 'Edition'},
                    'locales': {'fr': join_url('views/edit/tpl-edit_fr.json')}
                    }, {
                    'path': join_url('tpl-view.html', path=self.html_path),
                    'values': {'fr': 'Vue'},
                    'locales': {'fr': join_url('views/view/tpl-view_fr.json')}
                    }]},
            'models': {
                'list': [{
                    'path': join_url(self.model_json),
                    'value': 'Modèle de fiche vierge'
                    }]},
            'locales': self.locales,
            'locales_path': join_url('locales/'),
            'geographicextents_list': join_url('list_geographicextents.json'),
            'referencesystems_list': join_url('list_referencesystems.json'),
            'static_root': join_url('libs/mdedit/', path=STATIC_URL),
            'modal_template': {
                'help': join_url('modal-help.html', path='mdedit/html/')}}

        context = {'dataset_name': three_suspension_points(dataset.name),
                   'dataset_id': dataset.id,
                   'doc_url': READTHEDOC_URL_INSPIRE,
                   'config': config}

        if dataset.geonet_id:
            record = geonet.get_record(str(dataset.geonet_id))
            xml = record.xml.decode(encoding='utf-8')
            context['record_xml'] = re.sub('\n', '', xml).replace("'", "\\'")  # C'est moche
        else:
            context['record_obj'] = \
                prefill_model(open_json_staticfile(
                    os.path.join(self.config_path, self.model_json)), dataset)

        return render_with_info_profile(request, self.template, context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, dataset_id, *args, **kwargs):

        user, profile = user_and_profile(request)

        dataset = get_object_or_404_extended(
            Dataset, user, include={'id': dataset_id})

        def http_redirect(dataset_id):
            return HttpResponseRedirect(
                reverse(self.namespace, kwargs={'dataset_id': dataset_id}))

        if not request.is_ajax():
            return http_redirect(dataset_id)

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
                dataset.save()
                try:
                    publish_dataset_to_ckan(user, dataset)
                except Exception:
                    messages.error(request, 'Une erreur de synchronisation avec CKan est survenue.')
                else:
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
