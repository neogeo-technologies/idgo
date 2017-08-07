from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.models import License


@method_decorator([csrf_exempt, ], name='dispatch')
class DisplayLicenses(View):

    def get(self, request):
        data = [{
            'domain_content': o.domain_content,
            'domain_data': o.domain_data,
            'domain_software': o.domain_software,
            'family': '',  # TODO ???
            'id': o.id,
            'maintainer': o.maintainer,
            'od_conformance': o.od_conformance,
            'osd_conformance': o.osd_conformance,
            'status': o.status,
            'title': o.title,
            'url': o.url} for o in License.objects.all()]
        return JsonResponse(data, safe=False)
