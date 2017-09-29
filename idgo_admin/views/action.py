from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.models import Dataset


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class ActionsManager(View):

    @ExceptionsHandler(ignore=[Http404])
    def get(self, request):
        dataset_id = request.GET.get("id", None)
        publish = request.GET.get("publish", "")

        user = request.user
        if not dataset_id or not publish.lower() in ['true', 'yes', 'oui', 'vrai', '1']:
            return JsonResponse({"success": False,
                                 "action": "What you mean by {}?".format(publish)}, status=400)

        if dataset_id and publish.lower() in ['true', 'yes', 'oui', 'vrai', '1']:
            ds = get_object_or_404(Dataset, id=dataset_id, editor=user)
            ds.published = not ds.published
            ds.save()

        return JsonResponse({"success": True, "action": "Dataset publish state: {}".format(ds.published)}, status=200)
