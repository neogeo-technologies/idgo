from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
import functools
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


def creation_process(request, profile, mail=True):

    action = AccountActions.objects.create(
        action='confirm_new_organisation', profile=profile)

    mail and Mail.confirm_new_organisation(request, action)


def rattachement_process(request, profile, organisation, mail=True):

    action = AccountActions.objects.create(
        action='confirm_rattachement',
        org_extras=organisation, profile=profile)

    mail and Mail.confirm_updating_rattachement(request, action)


def contributor_process(request, profile, organisation, mail=True):

    LiaisonsContributeurs.objects.get_or_create(
        profile=profile, organisation=organisation)

    action = AccountActions.objects.create(
        action='confirm_contribution',
        org_extras=organisation, profile=profile)

    mail and Mail.confirm_contribution(request, action)


def referent_process(request, profile, organisation, mail=True):

    LiaisonsReferents.objects.get_or_create(
        organisation=organisation, profile=profile, validated_on=None)

    contributor_process(request, profile, organisation, mail=False)

    action = AccountActions.objects.create(
        action='confirm_referent',
        org_extras=organisation, profile=profile)

    mail and Mail.confirm_referent(request, action)


@method_decorator(decorators, name='dispatch')
class ThisOrganisation(View):

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id):
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
                    organisation=id, id=member.id) and True or False,
                'is_contributor': LiaisonsContributeurs.objects.filter(
                    profile=member, organisation__id=id) and True or False,
                'is_referent': LiaisonsReferents.objects.filter(
                    profile=member, organisation__id=id) and True or False,
                'datasets_count': len(Dataset.objects.filter(
                    organisation=id, editor=member.user)),
                'profile_id': member.id
                } for member in Profile.objects.filter(
                    functools.reduce(operator.or_, [
                        Q(organisation=id),
                        Q(liaisonscontributeurs__organisation=id),
                        Q(liaisonsreferents__organisation=id)])
                    ).distinct().order_by('user__username')]}

        try:
            data['logo'] = urljoin(settings.DOMAIN_NAME, instance.logo.url)
        except ValueError:
            pass

        return JsonResponse(data=data, safe=False)


@method_decorator(decorators, name='dispatch')
class CreateOrganisation(View):
    template = 'idgo_admin/editorganization.html'
    namespace = 'idgo_admin:edit_organization'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request):
        user, profile = user_and_profile(request)
        context = {'form': Form(include={'user': user, 'extended': True})}

        return render_with_info_profile(
            request, self.template, context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request):
        user, profile = user_and_profile(request)

        form = Form(
            request.POST, request.FILES, include={'user': user})

        if not form.is_valid():
            return render_with_info_profile(
                request, self.template, context={'form': form})

        try:
            organisation = Organisation.objects.create(**dict(
                (item, form.cleaned_data[item]) for item in form.Meta.common_fields))
        except ValidationError as e:
            messages.error(request, str(e))
            return render_with_info_profile(
                request, self.template, context={'form': form})

        creation_process(request, profile)  # à revoir car cela ne fonctionne plus dans ce nouveau context

        # TODO: Factoriser
        form.cleaned_data.get('rattachement_process', False) \
            and rattachement_process(request, profile, organisation)
        form.cleaned_data.get('contributor_process', False) \
            and contributor_process(request, profile, organisation)
        form.cleaned_data.get('referent_process', False) \
            and referent_process(request, profile, organisation)

        messages.success(request, 'La demande a bien été envoyée.')

        return HttpResponseRedirect(reverse('idgo_admin:all_organizations'))


@method_decorator(decorators, name='dispatch')
class EditThisOrganisation(View):
    template = 'idgo_admin/editorganization.html'
    namespace = 'idgo_admin:edit_organization'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id):
        user, profile = user_and_profile(request)

        context = {
            'id': id,
            'form': Form(
                instance=get_object_or_404(Organisation, id=id),
                include={'user': user, 'id': id})}

        return render_with_info_profile(
            request, self.template, context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, id):
        user, profile = user_and_profile(request)

        instance = get_object_or_404(Organisation, id=id)

        form = Form(request.POST, request.FILES,
                    instance=instance, include={'user': user, 'id': id})

        if not form.is_valid():
            raise Exception

        for item in form.Meta.fields:
            setattr(instance, item, form.cleaned_data[item])
        instance.save()

        return render_with_info_profile(
            request, self.template, context={'id': id, 'form': form})


@method_decorator(decorators, name='dispatch')
class AllOrganisations(View):

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):
        user, profile = user_and_profile(request)

        organizations = [{
            'pk': item.pk,
            'name': item.name,
            'rattachement': item == profile.organisation,
            'contributeur': item in Organisation.objects.filter(liaisonscontributeurs__profile=profile),
            'subordinates': item in Organisation.objects.filter(liaisonsreferents__profile=profile),
            } for item in Organisation.objects.all()]

        organizations.sort(key=operator.itemgetter('contributeur'), reverse=True)
        organizations.sort(key=operator.itemgetter('subordinates'), reverse=True)
        organizations.sort(key=operator.itemgetter('rattachement'), reverse=True)

        return render_with_info_profile(
            request, 'idgo_admin/all_organizations.html',
            context={'organizations': organizations})
