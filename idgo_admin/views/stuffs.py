from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.models import License


@method_decorator([csrf_exempt, ], name='dispatch')
class DisplayLicenses(View):

    def get(self, request):
        data = [{
            'domain_content': license.domain_content,
            'domain_data': license.domain_data,
            'domain_software': license.domain_software,
            'family': '',  # TODO?
            'id': 'license-{0}'.format(license.id),  # Ugly
            'maintainer': license.maintainer,
            'od_conformance': license.od_conformance,
            'osd_conformance': license.osd_conformance,
            'status': license.status,
            'title': license.title,
            'url': license.url} for license in License.objects.all()]
        return JsonResponse(data, safe=False)
