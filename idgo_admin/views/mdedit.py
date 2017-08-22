from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.models import Dataset
from idgo_admin.utils import three_suspension_points
from urllib.parse import urljoin


STATIC_URL = settings.STATIC_URL
GEONETWORK_URL = settings.GEONETWORK_URL

decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


def get_list_xml():
    pass


def get_url():

    pass


def get_xml():
    pass


def send_xml():
    pass


@method_decorator(decorators, name='dispatch')
class MDEditTplEdit(View):

    template = 'idgo_admin/mdedit/template_edit.html'

    def get(self, request, dataset_id):

        def join_url(filename, path='html/mdedit/'):
            return urljoin(urljoin(STATIC_URL, path), filename)

        user = request.user
        dataset = get_object_or_404(Dataset, id=dataset_id, editor=user)

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

    def get(self, request, dataset_id):

        user = request.user
        dataset = get_object_or_404(Dataset, id=dataset_id, editor=user)

        def join_url(filename, path='libs/mdedit/config/'):
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
                    'path': join_url('models/model-empty.json'),
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

        return render(request, self.template, context=context)
