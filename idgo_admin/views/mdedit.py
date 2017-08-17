from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.models import Dataset
from idgo_admin.utils import three_suspension_points
from urllib.parse import urljoin


STATIC_URL = urljoin(settings.STATIC_URL, 'libs/mdedit/')

decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class MDEditTplEdit(View):
    template = 'idgo_admin/mdedit/tpl-edit.html'

    def get(self, request, dataset_id):

        user = request.user
        dataset = get_object_or_404(Dataset, id=dataset_id, editor=user)

        tpl_base_path = urljoin(STATIC_URL, 'app/mdEdit.directives/edit/partials/')

        context = {
            'dataset_id': dataset_id,
            'template': {
                'edit_accordion_header': urljoin(tpl_base_path, 'editAccordionHeader.html'),
                'edit_contacts': urljoin(tpl_base_path, 'editContacts.html'),
                'edit_data_browsegraphics': urljoin(tpl_base_path, 'editDataBrowsegraphics.html'),
                'edit_data_distribution_formats': urljoin(tpl_base_path, 'editDataDistributionFormats.html'),
                'edit_data_geographic_extents': urljoin(tpl_base_path, 'editDataGeographicExtents.html'),
                'edit_data_identifiers': urljoin(tpl_base_path, 'editDataIdentifiers.html'),
                'edit_data_keywords': urljoin(tpl_base_path, 'editDataKeywords.html'),
                'edit_data_linkages': urljoin(tpl_base_path, 'editDataLinkages.html'),
                'edit_data_reference_systems': urljoin(tpl_base_path, 'editDataReferenceSystems.html'),
                'edit_data_temporal_extents': urljoin(tpl_base_path, 'editDataTemporalExtents.html'),
                'edit_date': urljoin(tpl_base_path, 'editDate.html'),
                'edit_input': urljoin(tpl_base_path, 'editInput.html'),
                'edit_multi_select': urljoin(tpl_base_path, 'editMultiSelect.html'),
                'edit_multi_textarea': urljoin(tpl_base_path, 'editMultiTextarea.html'),
                'edit_select': urljoin(tpl_base_path, 'editSelect.html'),
                'edit_textarea': urljoin(tpl_base_path, 'editTextarea.html')}}

        return render(request, self.template, context=context)


@method_decorator(decorators, name='dispatch')
class MDEdit(View):

    template = 'idgo_admin/mdedit/base.html'

    def get(self, request, dataset_id):

        user = request.user
        dataset = get_object_or_404(Dataset, id=dataset_id, editor=user)
        views_file = urljoin(STATIC_URL, 'config/views/views.json')
        models_file = urljoin(STATIC_URL, 'config/models/models.json')
        locales_path = urljoin(STATIC_URL, 'config/locales/')
        geographicextents_list = \
            urljoin(STATIC_URL, 'config/list_geographicextents.json')
        referencesystems_list = \
            urljoin(STATIC_URL, 'config/list_referencesystems.json')

        context = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'dataset_name': three_suspension_points(dataset.name),
            'dataset_id': dataset.id,
            'config': {
                'app_name': 'mdEdit',
                'app_title': 'mdEdit',
                'app_version': '0.14.9~hacked',
                'app_copyrights': '(c) CIGAL 2016',
                'defaultLanguage': 'fr',
                'server_url_getxml': '',
                'server_url_geturl': '',
                'server_url_sendxml': '',
                'server_url_getlistxml': '',
                'server_url_md': '',
                'views_file': views_file,
                'models_file': models_file,
                'locales_path': locales_path,
                'geographicextents_list': geographicextents_list,
                'referencesystems_list': referencesystems_list,
                'static_url': STATIC_URL}}

        return render(request, self.template, context=context)
