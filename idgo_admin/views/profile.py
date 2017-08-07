from django.conf import settings
from django.contrib.auth.decorators import login_required

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from idgo_admin.models import Dataset
from idgo_admin.models import Liaisons_Contributeurs
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
import json


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def home(request):

    user = request.user
    datasets = [(
        o.pk,
        o.name,
        o.date_creation.isoformat() if o.date_creation else None,
        o.date_modification.isoformat() if o.date_modification else None,
        o.date_publication.isoformat() if o.date_publication else None,
        Organisation.objects.get(id=o.organisation_id).name,
        o.published) for o in Dataset.objects.filter(editor=user)]

    # Cas ou l'user existe mais pas le profile
    try:
        profile = Profile.objects.get(user=user)
    except Exception:
        logout(request)
        return redirect('idgo_admin:signIn')

    my_contributions = Liaisons_Contributeurs.get_contribs(profile=profile)
    is_contributor = len(my_contributions) > 0

    return render(request, 'idgo_admin/home.html',
                  {'first_name': user.first_name,
                   'last_name': user.last_name,
                   'datasets': json.dumps(datasets),
                   'is_contributor': json.dumps(is_contributor)}, status=200)
