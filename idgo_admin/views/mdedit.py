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
from idgo_admin.geonet_module import GeonetUserHandler as geonet
from idgo_admin.models import Dataset
from idgo_admin.models import Resource
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
STATICFILES_DIRS = settings.STATICFILES_DIRS
DOMAIN_NAME = settings.DOMAIN_NAME


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


def get_list_xml(*args, **kwargs):
    raise Http404


def get_url(*args, **kwargs):
    raise Http404


def get_xml(*args, **kwargs):
    raise Http404


def send_xml(*args, **kwargs):
    raise Http404


def prefill_model(model, dataset):
    data = model.copy()

    editor = dataset.editor
    organization = dataset.organisation

    data['mdContacts'][0].update({
        'individualName': editor.get_full_name(),
        'organisationName': organization.name,
        'email': organization.email,
        'deliveryPoint': organization.adresse,
        'postalCode': organization.code_postal,
        'city': dataset.organisation.ville})

    try:
        data['mdContacts'][0].update({
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

    resources = Resource.objects.filter(dataset=dataset)
    for resource in resources:
        data['dataLinkages'].insert(0, {
            'name': resource.name,
            'description': resource.description})

    return clean_my_obj(data)


@method_decorator(decorators, name='dispatch')
class MDEditTplEdit(View):

    template = 'idgo_admin/mdedit/template_edit.html'

    def get(self, request, dataset_id):

        def join_url(filename, path='html/mdedit/'):
            return urljoin(urljoin(STATIC_URL, path), filename)

        user = request.user
        dataset = get_object_or_404(Dataset, id=dataset_id, editor=user)
        del dataset

        context = {
            'template': {
                'edit_accordion_header': join_url('editAccordionHeader.html'),
                'edit_contacts': join_url('editContacts.html'),
                'edit_data_browsegraphics': join_url('editDataBrowsegraphics.html'),
                'edit_data_distribution_formats': join_url('editDataDistributionFormats.html'),
                'edit_data_geographic_extents': join_url('editDataGeographicExtents.html'),
                'edit_data_identifiers': join_url('editDataIdentifiers.html'),
                'edit_data_keywords': join_url('editDataKeywords.html'),
                'edit_data_linkages': join_url('editDataLinkages.html'),
                'edit_data_reference_systems': join_url('editDataReferenceSystems.html'),
                'edit_data_temporal_extents': join_url('editDataTemporalExtents.html'),
                'edit_date': join_url('editDate.html'),
                'edit_input': join_url('editInput.html'),
                'edit_multi_select': join_url('editMultiSelect.html'),
                'edit_multi_textarea': join_url('editMultiTextarea.html'),
                'edit_select': join_url('editSelect.html'),
                'edit_textarea': join_url('editTextarea.html')}}

        return render(request, self.template, context=context)


@method_decorator(decorators, name='dispatch')
class MDEdit(View):

    template = 'idgo_admin/mdedit.html'
    namespace = 'idgo_admin:mdedit'
    config_path = 'libs/mdedit/config/'

    # filenames
    model_json = 'models/model-empty.json'

    def get(self, request, dataset_id):

        user = request.user
        dataset = get_object_or_404(Dataset, id=dataset_id, editor=user)

        def join_url(filename, path=self.config_path):
            return urljoin(urljoin(STATIC_URL, path), filename)

        def server_url(namespace):
            return reverse(
                'idgo_admin:{0}'.format(namespace), kwargs={'dataset_id': dataset.id})

        views = {
            'description': 'List of views',
            'list': [
                {
                    'path': 'mdedit/edit/',
                    'values': {
                        'fr': 'Edition'},
                    'locales': {
                        'fr': join_url('views/edit/tpl-edit_fr.json')}},
                {
                    'path': join_url('tpl-view.html', path='html/mdedit/'),
                    'values': {
                        'fr': 'Vue'},
                    'locales': {
                        'fr': join_url('views/view/tpl-view_fr.json')}},
                {
                    'path': join_url('views/listXml/tpl-listxml.html'),
                    'values': {
                        'fr': 'Liste XML'},
                    'locales': {
                        'fr': join_url('views/listXml/tpl-listxml_fr.json')}}]}

        models = {
            'description': 'List of default models',
            'list': [
                {
                    'path': join_url(self.model_json),
                    'value': 'Modèle de fiche vierge'},
                {
                    'path': join_url('models/model-cigal-opendata.json'),
                    'value': 'Modèle de fiche CIGAL (open data)'},
                {
                    'path': join_url('models/model-bdocs-cigal-2011-12.json'),
                    'value': 'Modèle de fiche BdOCS CIGAL 2011/12'}]}

        config = {
            'app_name': 'mdEdit',
            'app_title': 'mdEdit',
            'app_version': '0.14.9~hacked',
            'app_copyrights': '(c) CIGAL 2016',
            'defaultLanguage': 'fr',
            'server_url_getxml': server_url('mdedit_get_xml'),
            'server_url_geturl': server_url('mdedit_get_url'),
            'server_url_sendxml': server_url('mdedit_send_xml'),
            'server_url_getlistxml': server_url('mdedit_get_list_xml'),
            'server_url_md': GEONETWORK_URL,
            'views_file': views,
            'models_file': models,
            'locales_path': join_url('locales/'),
            'geographicextents_list': join_url('list_geographicextents.json'),
            'referencesystems_list': join_url('list_referencesystems.json'),
            'static_url': STATIC_URL,
            'modal_template': {
                'download': join_url('modal-download.html', path='html/mdedit/')}}

        context = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'dataset_name': three_suspension_points(dataset.name),
            'dataset_id': dataset.id,
            'config': config}

        if dataset.geonet_id:
            record = geonet.get_record(str(dataset.geonet_id))
            xml = record.xml.decode(encoding='utf-8')
            context['record_xml'] = re.sub('\n', '', xml).replace("'", "\\'")  # C'est moche
        else:
            context['record_json'] = prefill_model(open_json_staticfile(
                os.path.join(self.config_path, self.model_json)), dataset)

        return render(request, self.template, context=context)

    def post(self, request, dataset_id):

        user = request.user
        dataset = get_object_or_404(Dataset, id=dataset_id, editor=user)

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

        if not geonet.get_record(id):
            geonet.create_record(id, record)
            dataset.geonet_id = UUID(id)
            dataset.save()
        else:
            geonet.update_record(id, record)

        geonet.publish(id)  # Toujours publier la fiche

        messages.success(
            request, 'La fiche de metadonnées a été créé avec succès.')

        return HttpResponse()