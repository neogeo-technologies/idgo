from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.forms.account import ProfileUpdateForm
from idgo_admin.models import AccountActions
from idgo_admin.models import Liaisons_Contributeurs
from idgo_admin.models import Liaisons_Referents
from idgo_admin.models import Mail
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
import json


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def contribution_request(request):

    user = request.user
    profile = get_object_or_404(Profile, user=user)

    contribs = Liaisons_Contributeurs.get_contribs(profile=profile)

    if request.method == 'GET':
        return render(
            request, 'idgo_admin/contribute.html',
            {'first_name': user.first_name,
             'last_name': user.last_name,
             'pform': ProfileUpdateForm(exclude={'user': user}),
             'contribs': contribs})

    pform = ProfileUpdateForm(
        instance=profile, data=request.POST or None, exclude={'user': user})

    if not pform.is_valid():
        return render(request, 'idgo_admin/contribute.html', {'pform': pform})

    organisation = pform.cleaned_data['contributions']

    Liaisons_Contributeurs.objects.create(
        profile=profile, organisation=organisation)

    contribution_action = AccountActions.objects.create(
        profile=profile, action='confirm_contribution', org_extras=organisation)

    Mail.confirm_contribution(request, contribution_action)

    message = ("Votre demande de contribution à l'organisation "
               '<strong>{0}</strong> est en cours de traitement. Celle-ci '
               "ne sera effective qu'après validation par un administrateur."
               ).format(organisation.name)
    messages.success(request, message)

    return HttpResponseRedirect(reverse('idgo_admin:contribute'))


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def referent_request(request):

    user = request.user
    profile = get_object_or_404(Profile, user=user)

    subordonates = Liaisons_Referents.get_subordonates(profile=profile)

    if request.method == 'GET':
        return render(
            request, 'idgo_admin/contribute.html',
            {'first_name': user.first_name,
             'last_name': user.last_name,
             'pform': ProfileUpdateForm(exclude={'user': user}),
             'pub_liste': subordonates})

    pform = ProfileUpdateForm(
        instance=profile, data=request.POST or None, exclude={'user': user})

    if not pform.is_valid():
        return render(request, 'idgo_admin/contribute.html', {'pform': pform})

    organisation = pform.cleaned_data['referents']
    Liaisons_Referents.objects.create(
        profile=profile, organisation=organisation)
    request_action = AccountActions.objects.create(
        profile=profile, action='confirm_referent', org_extras=organisation)

    Mail.confirm_referent(request, request_action)

    return render(
        request, 'idgo_admin/contribute.html',
        {'first_name': user.first_name,
         'last_name': user.last_name,
         'pform': ProfileUpdateForm(exclude={'user': user}),
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

            if profile.organisation and profile.rattachement_active:
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
                    in Liaisons_Contributeurs.get_contribs(profile=profile)]

            awaiting_contributions = \
                [c.name for c
                    in Liaisons_Contributeurs.get_pending(profile=profile)]

            subordinates = \
                [(c.id, c.name) for c
                    in Liaisons_Referents.get_subordinates(profile=profile)]

            awaiting_subordinates = \
                [c.name for c
                    in Liaisons_Referents.get_pending(profile=profile)]

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

        organization_id = request.POST.get('id', request.GET.get('id')) or None

        if not organization_id:
                message = ("Une erreur critique s'est produite lors"
                           "de la suppression du status de contributeur"
                           "Merci de contacter l'administrateur du site")

                return render(request, 'idgo_admin/response.html',
                              {'message': message}, status=400)

        organization = Organisation.objects.get(id=organization_id)
        profile = get_object_or_404(Profile, user=request.user)

        my_contribution = Liaisons_Contributeurs.objects.get(
            profile=profile, organisation__id=organization_id)
        my_contribution.delete()
        # TODO(cbenhabib): send confirmation mail to user?

        context = {
            'action': reverse('idgo_admin:organizations'),
            'message': ("Vous n'êtes plus contributeur pour l'organisation "
                        "<strong>{0}</strong>").format(organization.name)}

        return render(
            request, 'idgo_admin/response.html', context=context, status=200)


@method_decorator([csrf_exempt, login_required(login_url=settings.LOGIN_URL)], name='dispatch')
class Referents(View):

    def get(self, request):
            user = request.user
            profile = get_object_or_404(Profile, user=user)
            my_subordinates = Liaisons_Referents.get_contribs(profile=profile)
            referents_tup = [(c.id, c.name) for c in my_subordinates]

            return render(
                request, 'idgo_admin/referents.html',
                context={'first_name': user.first_name,
                         'last_name': user.last_name,
                         'referents': json.dumps(referents_tup)})

    def delete(self, request):

        organization_id = request.POST.get('id', request.GET.get('id')) or None

        if not organization_id:
                message = ("Une erreur critique s'est produite lors"
                           "de la suppression du rôle de référent"
                           "Merci de contacter l'administrateur du site")

                return render(request, 'idgo_admin/response.html',
                              {'message': message}, status=400)

        organization = Organisation.objects.get(id=organization_id)
        profile = get_object_or_404(Profile, user=request.user)

        my_subordinates = Liaisons_Referents.objects.get(
            profile=profile, organisation__id=organization_id)
        my_subordinates.delete()

        context = {
            'action': reverse('idgo_admin:referents'),
            'message': ("Vous n'êtes plus contributeur pour l'organisation "
                        "<strong>{0}</strong>").format(organization.name)}

        return render(
            request, 'idgo_admin/response.html', context=context, status=200)
