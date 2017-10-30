from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import render
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
        user = request.user
        dataset_id = request.GET.get('id', None)
        publish = request.GET.get('publish', None)

        if dataset_id and publish.lower() == 'toggle':
            ds = get_object_or_404(Dataset, id=dataset_id, editor=user)
            ds.published = not ds.published
            message = (
                'Le jeu de données <strong>{0}</strong> '
                'est maintenant en accès <strong>{1}</strong>.'
                ).format(ds.name, ds.published and 'public' or 'privé')
            status = 200
            ds.save()

        return render(request, 'idgo_admin/response.html',
                      context={'message': message}, status=status)
