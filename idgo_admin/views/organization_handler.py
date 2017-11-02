from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
# from django.shortcuts import render
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
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def contribution_request(request, *args, **kwargs):

    user, profile = user_and_profile(request)

    process = 'update'
    template = 'idgo_admin/contribute.html'

    if request.method == 'GET':
        form = ProfileForm(include={'user': user, 'action': process})
        return render_with_info_profile(request, template, {'form': form})

    form = ProfileForm(instance=profile, data=request.POST,
                       include={'user': user, 'action': process})

    if not form.is_valid():
        return render_with_info_profile(request, template, {'form': form})

    organisation = form.cleaned_data['contributions']

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
def referent_request(request, *args, **kwargs):

    user, profile = user_and_profile(request)

    process = 'update'
    template = 'idgo_admin/referent.html'

    if request.method == 'GET':
        form = ProfileForm(include={'user': user, 'action': process})
        return render_with_info_profile(request, template, {'form': form})

    form = ProfileForm(instance=profile, data=request.POST or None,
                       include={'user': user, 'action': process})

    if not form.is_valid():
        return render_with_info_profile(request, template, {'form': form})

    organisation = form.cleaned_data['referents']

    LiaisonsReferents.objects.create(
        profile=profile, organisation=organisation)

    request_action = AccountActions.objects.create(
        profile=profile, action='confirm_referent', org_extras=organisation)

    Mail.confirm_referent(request, request_action)

    message = ("Votre demande de contribution à l'organisation "
               '<strong>{0}</strong> est en cours de traitement. Celle-ci '
               "ne sera effective qu'après validation par un administrateur."
               ).format(organisation.name)
    messages.success(request, message)

    return HttpResponseRedirect(reverse('idgo_admin:organizations'))


@method_decorator([csrf_exempt, login_required(login_url=settings.LOGIN_URL)], name='dispatch')
class OrganisationDisplay(View):

    def get(self, request, *args, **kwargs):

        return render_with_info_profile(
            request, 'idgo_admin/organizations.html')


@method_decorator([csrf_exempt, login_required(login_url=settings.LOGIN_URL)], name='dispatch')
class Contributions(View):

    def delete(self, request, *args, **kwargs):

        id = request.POST.get('id', request.GET.get('id')) or None
        if not id:
            return Http404()

        organization = get_object_or_404(Organisation, id=id)
        user, profile = user_and_profile(request)

        my_contribution = LiaisonsContributeurs.objects.get(
            profile=profile, organisation__id=id)
        my_contribution.delete()

        message = ("Vous n'êtes plus contributeur pour l'organisation "
                   "<strong>{0}</strong>").format(organization.name)

        messages.success(request, message)

        return HttpResponse(status=200)


@method_decorator([csrf_exempt, login_required(login_url=settings.LOGIN_URL)], name='dispatch')
class Referents(View):

    def delete(self, request, *args, **kwargs):

        id = request.POST.get('id', request.GET.get('id')) or None
        if not id:
            return Http404()

        organization = get_object_or_404(Organisation, id=id)
        user, profile = user_and_profile(request)

        my_subordinates = LiaisonsReferents.objects.get(
            profile=profile, organisation__id=id)
        my_subordinates.delete()

        message = ("Vous n'êtes plus référent pour l'organisation "
                   "<strong>{0}</strong>").format(organization.name)

        messages.success(request, message)

        return HttpResponse(status=200)
