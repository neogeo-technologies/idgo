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
from idgo_admin.forms.account import ProfileForm
from idgo_admin.models import AccountActions
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import Mail
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
import json


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def contribution_request(request):

    user = request.user
    profile = get_object_or_404(Profile, user=user)
    process = 'update'
    contribs = LiaisonsContributeurs.get_contribs(profile=profile)

    if request.method == 'GET':
        return render(
            request, 'idgo_admin/contribute.html',
            {'first_name': user.first_name,
             'last_name': user.last_name,
             'pform': ProfileForm(include={'user': user, 'action': process}),
             'contribs': contribs})

    pform = ProfileForm(
        instance=profile, data=request.POST or None,
        include={'user': user, 'action': process})

    if not pform.is_valid():
        return render(request, 'idgo_admin/contribute.html', {'pform': pform})

    organisation = pform.cleaned_data['contributions']

    LiaisonsContributeurs.objects.create(
        profile=profile, organisation=organisation)

    contribution_action = AccountActions.objects.create(
        profile=profile, action='confirm_contribution', org_extras=organisation)

    Mail.confirm_contribution(request, contribution_action)

    message = ("Votre demande de contribution à l'organisation "
               '<strong>{0}</strong> est en cours de traitement. Celle-ci '
               "ne sera effective qu'après validation par un administrateur."
               ).format(organisation.name)
    messages.success(request, message)

    return HttpResponseRedirect(reverse('idgo_admin:organizations'))


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def referent_request(request):

    user = request.user
    profile = get_object_or_404(Profile, user=user)
    process = 'update'
    subordonates = LiaisonsReferents.get_subordonates(profile=profile)

    if request.method == 'GET':
        return render(
            request, 'idgo_admin/contribute.html',
            {'first_name': user.first_name,
             'last_name': user.last_name,
             'pform': ProfileForm(include={'user': user, 'action': process}),
             'pub_liste': subordonates})

    pform = ProfileForm(
        instance=profile, data=request.POST or None,
        include={'user': user, 'action': process})

    if not pform.is_valid():
        return render(request, 'idgo_admin/contribute.html', {'pform': pform})

    organisation = pform.cleaned_data['referents']
    LiaisonsReferents.objects.create(
        profile=profile, organisation=organisation)
    request_action = AccountActions.objects.create(
        profile=profile, action='confirm_referent', org_extras=organisation)

    Mail.confirm_referent(request, request_action)

    return render(
        request, 'idgo_admin/contribute.html',
        {'first_name': user.first_name,
         'last_name': user.last_name,
         'pform': ProfileForm(include={'user': user, 'action': process}),
         'pub_liste': subordonates,
         'message': {
             'status': 'success',
             'text': (
                 "Votre demande de contribution à l'organisation "
                 '<strong>{0}</strong> est en cours de traitement. Celle-ci '
                 "ne sera effective qu'après validation par un administrateur."
                 ).format(organisation.name)}})


@method_decorator([csrf_exempt, login_required(login_url=settings.LOGIN_URL)], name='dispatch')
class Contributions(View):

    def get(self, request):
            user = request.user
            profile = get_object_or_404(Profile, user=user)

            if profile.organisation and profile.membership:
                organization = profile.organisation.name
            else:
                organization = None

            try:
                action = AccountActions.objects.get(
                    action='confirm_rattachement',
                    profile=profile, closed__isnull=True)
            except Exception:
                awaiting_rattachement = None
            else:
                awaiting_rattachement = \
                    action.org_extras.name if action.org_extras else None

            contributions = \
                [(c.id, c.name) for c
                    in LiaisonsContributeurs.get_contribs(profile=profile)]

            awaiting_contributions = \
                [c.name for c
                    in LiaisonsContributeurs.get_pending(profile=profile)]

            subordinates = \
                [(c.id, c.name) for c
                    in LiaisonsReferents.get_subordinates(profile=profile)]

            awaiting_subordinates = \
                [c.name for c
                    in LiaisonsReferents.get_pending(profile=profile)]

            return render(
                request, 'idgo_admin/organizations.html',
                context={'first_name': user.first_name,
                         'last_name': user.last_name,
                         'organization': organization,
                         'awaiting_organization': awaiting_rattachement,
                         'contributions': json.dumps(contributions),
                         'awaiting_contributions': awaiting_contributions,
                         'subordinates': json.dumps(subordinates),
                         'awaiting_subordinates': awaiting_subordinates})

    def delete(self, request):

        id = request.POST.get('id', request.GET.get('id')) or None
        if not id:
            return Http404()

        organization = Organisation.objects.get(id=id)
        profile = get_object_or_404(Profile, user=request.user)

        my_contribution = LiaisonsContributeurs.objects.get(
            profile=profile, organisation__id=id)
        my_contribution.delete()

        message = ("Vous n'êtes plus contributeur pour l'organisation "
                   "<strong>{0}</strong>").format(organization.name)

        messages.success(request, message)

        # return render(request, 'idgo_admin/response.html',
        #               context={'message': message}, status=200)

        return HttpResponse(status=status)


@method_decorator([csrf_exempt, login_required(login_url=settings.LOGIN_URL)], name='dispatch')
class Referents(View):

    def get(self, request):
            user = request.user
            profile = get_object_or_404(Profile, user=user)
            my_subordinates = LiaisonsReferents.get_contribs(profile=profile)
            referents_tup = [(c.id, c.name) for c in my_subordinates]

            return render(
                request, 'idgo_admin/referents.html',
                context={'first_name': user.first_name,
                         'last_name': user.last_name,
                         'referents': json.dumps(referents_tup)})

    def delete(self, request):

        id = request.POST.get('id', request.GET.get('id')) or None
        if not id:
            return Http404()

        organization = Organisation.objects.get(id=id)
        profile = get_object_or_404(Profile, user=request.user)

        my_subordinates = LiaisonsReferents.objects.get(
            profile=profile, organisation__id=id)
        my_subordinates.delete()

        message = ("Vous n'êtes plus référent pour l'organisation "
                   "<strong>{0}</strong>").format(organization.name)

        messages.success(request, message)

        # return render(request, 'idgo_admin/response.html',
        #               context={'message': message}, status=200)

        return HttpResponse(status=status)
