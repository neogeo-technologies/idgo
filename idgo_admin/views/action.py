from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.dataset import publish_dataset_to_ckan
from idgo_admin.models import Dataset
from idgo_admin.shortcuts import get_object_or_404_extended
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import user_and_profile


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class ActionsManager(View):

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)

        dataset_id = request.GET.get('id', None)
        publish = request.GET.get('publish', None)

        if dataset_id and publish.lower() == 'toggle':
            dataset = get_object_or_404_extended(
                Dataset, user, include={'id': dataset_id})

            dataset.published = not dataset.published

            try:
                ckan_uuid = publish_dataset_to_ckan(user, dataset)
            except Exception as e:
                raise e
            else:
                dataset.ckan_id = ckan_uuid
                dataset.save()

            message = (
                'Le jeu de données <strong>{0}</strong> '
                'est maintenant en accès <strong>{1}</strong>.'
                ).format(dataset.name, dataset.published and 'public' or 'privé')
            status = 200

        return render(request, 'idgo_admin/response.html',
                      context={'message': message}, status=status)
