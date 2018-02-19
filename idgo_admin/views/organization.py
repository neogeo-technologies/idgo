from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
# from django.db import transaction
from django.http import Http404
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
import functools
from idgo_admin.ckan_module import CkanSyncingError
from idgo_admin.ckan_module import CkanTimeoutError
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.organization import OrganizationForm as Form
from idgo_admin.models import AccountActions
from idgo_admin.models import Dataset
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import Mail
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
import operator
from urllib.parse import urljoin


CKAN_URL = settings.CKAN_URL

decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


def creation_process(request, profile, organisation, mail=True):
    action = AccountActions.objects.create(
        action='confirm_new_organisation',
        organisation=organisation,
        profile=profile)
    mail and Mail.confirm_new_organisation(request, action)


def member_subscribe_process(request, profile, organisation, mail=True):
    action = AccountActions.objects.create(
        action='confirm_rattachement',
        organisation=organisation,
        profile=profile)
    mail and Mail.confirm_updating_rattachement(request, action)


def member_unsubscribe_process(request, profile, organisation):
    if profile.organisation != organisation:
        raise Exception('TODO')
    profile.organisation = None
    profile.membership = False
    profile.save()


def contributor_subscribe_process(request, profile, organisation, mail=True):
    LiaisonsContributeurs.objects.get_or_create(
        profile=profile,
        organisation=organisation)
    action = AccountActions.objects.create(
        action='confirm_contribution',
        organisation=organisation,
        profile=profile)
    mail and Mail.confirm_contribution(request, action)


def contributor_unsubscribe_process(request, profile, organisation):
    LiaisonsContributeurs.objects.get(
        organisation=organisation, profile=profile).delete()


def referent_subscribe_process(request, profile, organisation, mail=True):
    if not LiaisonsContributeurs.objects.filter(
            organisation=organisation, profile=profile).exists():
        contributor_subscribe_process(request, profile, organisation, mail=mail)

    LiaisonsReferents.objects.get_or_create(
        organisation=organisation, profile=profile, validated_on=None)
    action = AccountActions.objects.create(
        action='confirm_referent',
        organisation=organisation, profile=profile)
    mail and Mail.confirm_referent(request, action)


def referent_unsubscribe_process(request, profile, organisation):
    LiaisonsReferents.objects.get(
        organisation=organisation, profile=profile).delete()


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def all_organisations(request, *args, **kwargs):

    user, profile = user_and_profile(request)

    organizations = [{
        'pk': item.pk,
        'name': item.name,
        'rattachement': item == profile.organisation,
        'contributeur':
            item in Organisation.objects.filter(
                liaisonscontributeurs__profile=profile,
                liaisonscontributeurs__validated_on__isnull=False),
        'subordinates':
            profile.is_admin and True or item in Organisation.objects.filter(
                liaisonsreferents__profile=profile,
                liaisonscontributeurs__validated_on__isnull=False),
        } for item in Organisation.objects.filter(is_active=True)]

    organizations.sort(key=operator.itemgetter('contributeur'), reverse=True)
    organizations.sort(key=operator.itemgetter('subordinates'), reverse=True)
    organizations.sort(key=operator.itemgetter('rattachement'), reverse=True)

    return render_with_info_profile(
        request, 'idgo_admin/all_organizations.html',
        context={'organizations': organizations})


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def organisation(request, id=None):

    user, profile = user_and_profile(request)

    instance = get_object_or_404(Organisation, id=id, is_active=True)

    data = {
        'id': instance.id,
        'name': instance.name,
        # logo -> see below
        'type': instance.organisation_type,
        'jurisdiction':
            instance.jurisdiction and instance.jurisdiction.name or '',
        'address': instance.address,
        'postcode': instance.postcode,
        'city': instance.city,
        'phone': instance.org_phone,
        'website': instance.website,
        'email': instance.email,
        'description': instance.description,
        'members': [{
            'username': member.user.username,
            'full_name': member.user.get_full_name(),
            'is_member': Profile.objects.filter(
                organisation=id, id=member.id).exists(),
            'is_contributor': LiaisonsContributeurs.objects.filter(
                profile=member, organisation__id=id, validated_on__isnull=False
                ).exists(),
            'is_referent': LiaisonsReferents.objects.filter(
                profile=member, organisation__id=id, validated_on__isnull=False
                ).exists(),
            'datasets_count': len(Dataset.objects.filter(
                organisation=id, editor=member.user)),
            'profile_id': member.id
            } for member in Profile.objects.filter(
                functools.reduce(operator.or_, [
                    Q(organisation=id),
                    functools.reduce(operator.and_, [
                        Q(liaisonscontributeurs__organisation=id),
                        Q(liaisonscontributeurs__validated_on__isnull=False)]),
                    functools.reduce(operator.and_, [
                        Q(liaisonsreferents__organisation=id),
                        Q(liaisonsreferents__validated_on__isnull=False)])])
                ).distinct().order_by('user__username')]}

    try:
        data['logo'] = urljoin(settings.DOMAIN_NAME, instance.logo.url)
    except ValueError:
        pass

    return JsonResponse(data=data, safe=False)


@method_decorator(decorators, name='dispatch')
class CreateOrganisation(View):

    template = 'idgo_admin/organization.html'

    @ExceptionsHandler(
        ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request):
        user, profile = user_and_profile(request)
        context = {'form': Form(include={'user': user, 'extended': True})}

        return render_with_info_profile(
            request, self.template, context=context)

    @ExceptionsHandler(
        ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request):
        user, profile = user_and_profile(request)

        form = Form(
            request.POST, request.FILES, include={'user': user})

        if not form.is_valid():
            return render_with_info_profile(
                request, self.template, context={'form': form})

        try:
            organisation = Organisation.objects.create(**dict(
                (item, form.cleaned_data[item])
                for item in form.Meta.organisation_fields))
        except ValidationError as e:
            messages.error(request, str(e))
            return render_with_info_profile(
                request, self.template, context={'form': form})

        creation_process(request, profile, organisation)  # à revoir car cela ne fonctionne plus dans ce nouveau context

        form.cleaned_data.get('rattachement_process', False) \
            and member_subscribe_process(request, profile, organisation)

        # Dans le cas ou seul le role de contributeur est demandé
        form.cleaned_data.get('contributor_process', False) \
            and not form.cleaned_data.get('referent_process', False) \
            and contributor_subscribe_process(request, profile, organisation)

        # role de référent requis donc role de contributeur requis
        form.cleaned_data.get('referent_process', False) \
            and referent_subscribe_process(request, profile, organisation)

        messages.success(request, 'La demande a bien été envoyée.')

        return HttpResponseRedirect(reverse('idgo_admin:all_organizations'))


@method_decorator(decorators, name='dispatch')
class UpdateOrganisation(View):
    template = 'idgo_admin/organization.html'

    @ExceptionsHandler(
        ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id=None):
        user, profile = user_and_profile(request)

        is_admin = profile.is_admin
        is_referent = LiaisonsReferents.objects.filter(
            profile=profile, organisation__id=id,
            validated_on__isnull=False) and True or False

        if is_referent or is_admin:
            return render_with_info_profile(
                request, self.template, context={
                    'id': id, 'update': True, 'form': Form(
                        instance=get_object_or_404(Organisation, id=id),
                        include={'user': user, 'id': id})})

        raise Http404()

    @ExceptionsHandler(
        ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, id=None):
        user, profile = user_and_profile(request)

        instance = get_object_or_404(Organisation, id=id)
        form = Form(request.POST, request.FILES,
                    instance=instance, include={'user': user, 'id': id})

        if not form.is_valid():
            return render_with_info_profile(
                request, self.template, context={'id': id, 'form': form})

        for item in form.Meta.fields:
            setattr(instance, item, form.cleaned_data[item])
        try:
            instance.save()
        except CkanSyncingError:
            messages.error(request, 'Une erreur de synchronisation avec CKAN est survenue.')
        except CkanTimeoutError:
            messages.error(request, 'Impossible de joindre CKAN.')
        else:
            messages.success(
                request, "L'organisation a été mise à jour avec succès.")

        if 'continue' in request.POST:
            context = {
                'id': id,
                'update': True,
                'form': Form(
                    instance=instance, include={'user': user, 'id': id})}
            return render_with_info_profile(
                request, self.template, context=context)

        return HttpResponseRedirect('{0}#{1}'.format(
            reverse('idgo_admin:all_organizations'), instance.id))


@method_decorator(decorators, name='dispatch')
class Subscription(View):

    namespace = 'idgo_admin:all_organizations'

    @ExceptionsHandler(
        ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, status=None, subscription=None):

        user, profile = user_and_profile(request)

        organisation = get_object_or_404(Organisation, id=request.GET.get('id'))

        actions = {
            'member': {
                'subscribe': member_subscribe_process,
                'unsubscribe': member_unsubscribe_process},
            'contributor': {
                'subscribe': contributor_subscribe_process,
                'unsubscribe': contributor_unsubscribe_process},
            'referent': {
                'subscribe': referent_subscribe_process,
                'unsubscribe': referent_unsubscribe_process}}

        try:
            actions[status][subscription](request, profile, organisation)
        except Exception as e:
            messages.error(request, str(e))
        else:
            if subscription == 'unsubscribe':
                message = (
                    "Vous n'êtes plus {0} de l'organisation <strong>{1}</strong>."
                    ).format(status, organisation.name)
            elif subscription == 'subscribe':
                message = (
                    "Votre demande de statut de {0} de l'organisation "
                    '<strong>{0}</strong> est en cours de traitement. '
                    "Celle-ci ne sera effective qu'après validation par "
                    'un administrateur.').format(status, organisation.name)
            messages.success(request, message)

        return HttpResponseRedirect('{0}#{1}'.format(
            reverse(self.namespace), organisation.id))
