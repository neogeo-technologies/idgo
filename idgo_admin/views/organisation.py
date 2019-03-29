# Copyright (c) 2017-2019 Datasud.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db import transaction
from django.http import Http404
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
import functools
from idgo_admin.ckan_module import CkanBaseHandler
# from idgo_admin.csw_module import CswBaseHandler
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.exceptions import CswBaseError
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import GenericException
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.organisation import OrganisationForm as Form
from idgo_admin.forms.organisation import RemoteCkanForm
from idgo_admin.forms.organisation import RemoteCswForm
from idgo_admin.models import AccountActions
from idgo_admin.models import Dataset
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models.mail import send_contributor_confirmation_mail
from idgo_admin.models.mail import send_mail_asking_for_crige_partnership
from idgo_admin.models.mail import send_membership_confirmation_mail
from idgo_admin.models.mail import send_organisation_creation_confirmation_mail
from idgo_admin.models.mail import send_referent_confirmation_mail
from idgo_admin.models import Category
from idgo_admin.models import License
from idgo_admin.models import MappingCategory
from idgo_admin.models import MappingLicence
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.models import RemoteCkan
from idgo_admin.models import RemoteCsw
from idgo_admin.models import SupportedCrs
from idgo_admin.mra_client import MRAHandler
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
    if mail:
        url = request.build_absolute_uri(
            reverse('idgo_admin:confirm_new_orga', kwargs={'key': action.key}))
        send_organisation_creation_confirmation_mail(profile.user, organisation, url)
    return action


def member_subscribe_process(request, profile, organisation, mail=True):
    action = AccountActions.objects.create(
        action='confirm_rattachement',
        organisation=organisation,
        profile=profile)

    if mail:
        url = request.build_absolute_uri(
            reverse('idgo_admin:confirm_rattachement', kwargs={'key': action.key}))
        send_membership_confirmation_mail(profile.user, organisation, url)
    return action


def member_unsubscribe_process(request, profile, organisation):
    if profile.organisation != organisation:
        raise GenericException()
    if profile.organisation.is_crige_partner:
        profile.crige_membership = False
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
    if mail:
        url = request.build_absolute_uri(
            reverse('idgo_admin:confirm_contribution', kwargs={'key': action.key}))
        send_contributor_confirmation_mail(profile.user, organisation, url)
    return action


def contributor_unsubscribe_process(request, profile, organisation):
    LiaisonsContributeurs.objects.get(
        organisation=organisation, profile=profile).delete()


def referent_subscribe_process(request, profile, organisation, mail=True):
    if not LiaisonsContributeurs.objects.filter(
            organisation=organisation, profile=profile).exists():
        contributor_subscribe_process(request, profile, organisation, mail=False)

    LiaisonsReferents.objects.get_or_create(
        organisation=organisation, profile=profile, validated_on=None)
    action = AccountActions.objects.create(
        action='confirm_referent',
        organisation=organisation, profile=profile)

    if mail:
        url = request.build_absolute_uri(
            reverse('idgo_admin:confirm_referent', kwargs={'key': action.key}))
        send_referent_confirmation_mail(profile.user, organisation, url)
    return action


def referent_unsubscribe_process(request, profile, organisation):
    LiaisonsReferents.objects.get(
        organisation=organisation, profile=profile).delete()


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def all_organisations(request, *args, **kwargs):

    user, profile = user_and_profile(request)

    organisations = [{
        'contributor':
            item in Organisation.objects.filter(
                liaisonscontributeurs__profile=profile,
                liaisonscontributeurs__validated_on__isnull=False),
        'legal_name': item.legal_name,
        'member': item == profile.organisation,
        'pk': item.pk,
        'referent':
            profile.is_admin and True or item in Organisation.objects.filter(
                liaisonsreferents__profile=profile,
                liaisonsreferents__validated_on__isnull=False),
        } for item in Organisation.objects.filter(is_active=True)]

    organisations.sort(key=operator.itemgetter('contributor'), reverse=True)
    organisations.sort(key=operator.itemgetter('referent'), reverse=True)
    organisations.sort(key=operator.itemgetter('member'), reverse=True)

    return render_with_info_profile(
        request, 'idgo_admin/organisation/organisations.html',
        context={
            'organisation_base_url': '/organisation',  # Moche
            'organisations': organisations})


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def organisation(request, id=None):

    user, profile = user_and_profile(request)

    instance = get_object_or_404(Organisation, id=id, is_active=True)

    data = {
        'id': instance.id,
        'legal_name': instance.legal_name,
        'crige': instance.is_crige_partner,
        # logo -> see below
        'type': instance.organisation_type and instance.organisation_type.name,
        'jurisdiction':
            instance.jurisdiction and instance.jurisdiction.name,
        'address': instance.address,
        'postcode': instance.postcode,
        'city': instance.city,
        'phone': instance.phone,
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
            'crige_membership': member.crige_membership,
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

    if instance.ows_url:
        ows_settings = MRAHandler.get_ows_settings('ows', instance.slug)
        data['osw'] = {
            'url': instance.ows_url,
            'title': ows_settings.pop('title', None),
            'abstract': ows_settings.pop('abstract', None)}

    try:
        data['logo'] = urljoin(settings.DOMAIN_NAME, instance.logo.url)
    except ValueError:
        pass

    return JsonResponse(data=data, safe=False)


@ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def crige_partnership(request):
    id = request.GET.get('id')
    if not id:
        raise Http404()
    user, profile = user_and_profile(request)
    organisation = get_object_or_404(Organisation, id=id, is_active=True)
    send_mail_asking_for_crige_partnership(user, organisation)


@method_decorator(decorators, name='dispatch')
class CreateOrganisation(View):

    template = 'idgo_admin/organisation/edit.html'

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
            messages.error(request, e.__str__())
            return render_with_info_profile(
                request, self.template, context={'form': form})

        creation_process(request, profile, organisation)

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

        return HttpResponseRedirect(reverse('idgo_admin:all_organisations'))


@method_decorator(decorators, name='dispatch')
class UpdateOrganisation(View):
    template = 'idgo_admin/organisation/edit.html'

    @ExceptionsHandler(
        ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id=None):
        user, profile = user_and_profile(request)

        is_admin = profile.is_admin
        is_referent = LiaisonsReferents.objects.filter(
            profile=profile, organisation__id=id,
            validated_on__isnull=False) and True or False

        if is_referent or is_admin:
            instance = get_object_or_404(Organisation, id=id)
            return render_with_info_profile(
                request, self.template, context={
                    'id': id,
                    'update': True,
                    'organisation': instance,
                    'form': Form(instance=instance,
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
        except ValidationError as e:
            messages.error(request, e.__str__())
        except CkanBaseError as e:
            form.add_error('__all__', e.__str__())
            messages.error(request, e.__str__())
        else:
            messages.success(
                request, "L'organisation a été mise à jour avec succès.")

        if 'continue' in request.POST:
            context = {
                'id': id,
                'update': True,
                'organisation': instance,
                'form': Form(
                    instance=instance, include={'user': user, 'id': id})}
            return render_with_info_profile(
                request, self.template, context=context)

        return HttpResponseRedirect('{0}#{1}'.format(
            reverse('idgo_admin:all_organisations'), instance.id))


@method_decorator(decorators, name='dispatch')
class OrganisationOWS(View):

    @ExceptionsHandler(
        ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request):
        user, profile = user_and_profile(request)

        instance = get_object_or_404(Organisation, id=request.GET.get('id'))

        is_admin = profile.is_admin
        is_referent = LiaisonsReferents.objects.filter(
            profile=profile, organisation=instance,
            validated_on__isnull=False) and True or False

        if is_referent or is_admin:
            json = {
                'abstract': request.POST.get('abstract', None),
                'srs': [crs.authority for crs in SupportedCrs.objects.all()],
                'title': request.POST.get('title', None)}
            try:
                MRAHandler.update_ows_settings('ows', json, ws_name=instance.slug)
            except Exception as e:
                messages.error(request, e.__str__())
            else:
                messages.success(request, "Le service OGC est mis à jour.")
            return JsonResponse(data={})
        raise Http404()


@method_decorator(decorators, name='dispatch')
class Subscription(View):

    namespace = 'idgo_admin:all_organisations'

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

        status_fr_label = {
            'member': 'membre',
            'contributor': 'contributeur',
            'referent': 'référent'}

        try:
            actions[status][subscription](request, profile, organisation)
        except Exception as e:
            messages.error(request, str(e))
        else:
            if subscription == 'unsubscribe':
                message = (
                    "Vous n'êtes plus {} de l'organisation "
                    '« <strong>{}</strong> ».'
                    ).format(status_fr_label[status], organisation.legal_name)
            elif subscription == 'subscribe':
                message = (
                    'Votre demande de statut de <strong>{}</strong> de '
                    "l'organisation « <strong>{}</strong> » est en cours de "
                    "traitement. Celle-ci ne sera effective qu'après "
                    'validation par un administrateur.').format(
                        status_fr_label[status], organisation.legal_name)
                # Spécial CRIGE
                if status == 'member':
                    messages.info(request, "L'organisation est partenaire du CRIGE.")
                # Fin [Spécial CRIGE]
            messages.success(request, message)

        # TODO Revoir la gestion de l'AJAX sur la page des organisations

        return JsonResponse(data={})  # Bidon
        # return HttpResponseRedirect('{0}#{1}'.format(
        #     reverse(self.namespace), organisation.id))


# ========================
# MOISSONNAGE DE SITE CKAN
# ========================


@method_decorator(decorators, name='dispatch')
class RemoteCkanEditor(View):

    template = 'idgo_admin/organisation/remoteckan/edit.html'

    def get(self, request, id, *args, **kwargs):

        user, profile = user_and_profile(request)

        is_admin = profile.is_admin
        is_referent = LiaisonsReferents.objects.filter(
            profile=profile, organisation__id=id,
            validated_on__isnull=False) and True or False

        if is_referent or is_admin:
            organisation = get_object_or_404(Organisation, id=id)

            context = {'organisation': organisation}

            try:
                instance = RemoteCkan.objects.get(organisation=organisation)
            except RemoteCkan.DoesNotExist:
                form = RemoteCkanForm()
            else:
                context['datasets'] = Dataset.harvested_ckan.filter(organisation=organisation)
                context['instance'] = instance
                form = RemoteCkanForm(instance=instance)

            context['form'] = form

            return render_with_info_profile(
                request, self.template, context=context)

        raise Http404()

    def post(self, request, id, *args, **kwargs):

        user, profile = user_and_profile(request)

        is_admin = profile.is_admin
        is_referent = LiaisonsReferents.objects.filter(
            profile=profile, organisation__id=id,
            validated_on__isnull=False) and True or False

        if not(is_referent or is_admin):
            raise Http404()

        organisation = get_object_or_404(Organisation, id=id)

        context = {'organisation': organisation}

        url = request.POST.get('url')
        try:
            with transaction.atomic():
                instance, created = \
                    RemoteCkan.objects.get_or_create(
                        organisation=organisation, url=url)
        except CkanBaseError as e:
            form = RemoteCkanForm(request.POST)
            form.add_error('url', e.__str__())
        except ValidationError as e:
            form = RemoteCkanForm(request.POST)
            form.add_error(e.code, e.message)
        else:
            context['datasets'] = Dataset.harvested_ckan.filter(organisation=organisation)
            context['instance'] = instance
            form = RemoteCkanForm(request.POST, instance=instance)

        context['form'] = form

        if not form.is_valid():
            return render_with_info_profile(
                request, self.template, context=context)

        for k, v in form.cleaned_data.items():
            setattr(instance, k, v)
        try:
            with transaction.atomic():
                instance.save()
        except ValidationError as e:
            error = True
            messages.error(request, e.__str__())
        except CkanBaseError as e:
            error = True
            form.add_error('__all__', e.__str__())
            messages.error(request, e.__str__())
        else:
            error = False
            context['datasets'] = \
                Dataset.harvested_ckan.filter(organisation=organisation)
            context['form'] = RemoteCkanForm(instance=instance)
            if created:
                msg = "Veuillez indiquez les organisations distantes à moissonner."
            else:
                msg = 'Les informations de moissonnage ont été mises à jour.'
            messages.success(request, msg)

        def handle_mapping(request, form):
            mappings = form.Meta.mapping
            mapper = request.POST
            for mapping in mappings:
                if mapping.get('name') == 'Category':
                    MappingCategory.objects.filter(remote_ckan=instance).delete()
                    fields_name = mapping.get('fields_name')
                    data = dict(
                        filter(
                            lambda k: k[0] in fields_name,
                            mapper.dict().items())
                    )
                    not_empty = {k: v for k, v in data.items() if v}
                    for k, v in not_empty.items():
                        MappingCategory.objects.create(
                            remote_ckan=instance,
                            category=Category.objects.get(id=v),
                            slug=k
                        )
                if mapping.get('name') == 'License':
                    MappingLicence.objects.filter(remote_ckan=instance).delete()
                    fields_name = mapping.get('fields_name')
                    data = dict(
                        filter(
                            lambda k: k[0] in fields_name,
                            mapper.dict().items())
                    )
                    not_empty = {k: v for k, v in data.items() if v}
                    for k, v in not_empty.items():
                        MappingLicence.objects.create(
                            remote_ckan=instance,
                            licence=License.objects.get(slug=v),
                            slug=k
                        )

        try:
            with transaction.atomic():
                handle_mapping(request, form)
        except ValidationError as e:
            error = True
            messages.error(request, e.__str__())
        except CkanBaseError as e:
            error = True
            form.add_error('__all__', e.__str__())
            messages.error(request, e.__str__())

        if 'continue' in request.POST or error:
            return HttpResponseRedirect(
                reverse('idgo_admin:edit_remote_ckan_link', kwargs={'id': organisation.id}))

        return HttpResponseRedirect(
            reverse('idgo_admin:update_organisation', kwargs={'id': organisation.id}))


@method_decorator(decorators, name='dispatch')
class DeleteRemoteCkanLinked(View):

    def post(self, request, id, *args, **kwargs):

        user, profile = user_and_profile(request)

        is_admin = profile.is_admin
        is_referent = LiaisonsReferents.objects.filter(
            profile=profile, organisation__id=id,
            validated_on__isnull=False) and True or False

        if not(is_referent or is_admin):
            raise Http404()

        organisation = get_object_or_404(Organisation, id=id)
        instance = get_object_or_404(RemoteCkan, organisation=organisation)

        try:
            with transaction.atomic():
                instance.delete()
        except ValidationError as e:
            messages.error(request, e.__str__())
        except CkanBaseError as e:
            messages.error(request, e.__str__())
        else:
            messages.success(request, (
                'Les informations ainsi que les jeux de données et '
                'ressources synchronisés avec le catalogue distant '
                'ont été supprimés avec succès.'))

        return HttpResponseRedirect(
            reverse('idgo_admin:update_organisation', kwargs={'id': organisation.id}))


# =======================
# MOISSONNAGE DE SITE CSW
# =======================


@method_decorator(decorators, name='dispatch')
class RemoteCswEditor(View):

    template = 'idgo_admin/organisation/remotecsw/edit.html'

    def get(self, request, id, *args, **kwargs):

        user, profile = user_and_profile(request)

        is_admin = profile.is_admin
        is_referent = LiaisonsReferents.objects.filter(
            profile=profile, organisation__id=id,
            validated_on__isnull=False) and True or False

        if is_referent or is_admin:
            organisation = get_object_or_404(Organisation, id=id)

            context = {'organisation': organisation}

            try:
                instance = RemoteCsw.objects.get(organisation=organisation)
            except RemoteCsw.DoesNotExist:
                form = RemoteCswForm()
            else:
                context['datasets'] = Dataset.harvested_csw.filter(organisation=organisation)
                context['instance'] = instance
                form = RemoteCswForm(instance=instance)

            context['form'] = form

            return render_with_info_profile(
                request, self.template, context=context)

        raise Http404()

    def post(self, request, id, *args, **kwargs):

        user, profile = user_and_profile(request)

        is_admin = profile.is_admin
        is_referent = LiaisonsReferents.objects.filter(
            profile=profile, organisation__id=id,
            validated_on__isnull=False) and True or False

        if not(is_referent or is_admin):
            raise Http404()

        organisation = get_object_or_404(Organisation, id=id)

        context = {'organisation': organisation}

        url = request.POST.get('url')
        try:
            with transaction.atomic():
                instance, created = \
                    RemoteCsw.objects.get_or_create(
                        organisation=organisation, url=url)
        except CswBaseError as e:
            form = RemoteCswForm(request.POST)
            form.add_error('url', e.__str__())
        except ValidationError as e:
            form = RemoteCswForm(request.POST)
            form.add_error(e.code, e.message)
        else:
            context['datasets'] = Dataset.harvested_csw.filter(organisation=organisation)
            context['instance'] = instance
            form = RemoteCswForm(request.POST, instance=instance)

        context['form'] = form

        if not form.is_valid():
            messages.error(request, form._errors.__str__())
            return HttpResponseRedirect(
                reverse('idgo_admin:edit_remote_csw_link', kwargs={'id': organisation.id}))

        for k, v in form.cleaned_data.items():
            setattr(instance, k, v)
        try:
            with transaction.atomic():
                instance.save()
        except ValidationError as e:
            error = True
            messages.error(request, e.__str__())
        except CswBaseError as e:
            error = True
            form.add_error('__all__', e.__str__())
            messages.error(request, e.__str__())
        else:
            error = False
            context['datasets'] = \
                Dataset.harvested_csw.filter(organisation=organisation)
            context['form'] = RemoteCswForm(instance=instance)
            if created:
                msg = "Veuillez indiquez les organisations distantes à moissonner."
            else:
                msg = 'Les informations de moissonnage ont été mises à jour.'
            messages.success(request, msg)

        if 'continue' in request.POST or error:
            return render_with_info_profile(
                request, self.template, context=context)

        return HttpResponseRedirect(
            reverse('idgo_admin:update_organisation', kwargs={'id': organisation.id}))


@method_decorator(decorators, name='dispatch')
class DeleteRemoteCswLinked(View):

    def post(self, request, id, *args, **kwargs):

        user, profile = user_and_profile(request)

        is_admin = profile.is_admin
        is_referent = LiaisonsReferents.objects.filter(
            profile=profile, organisation__id=id,
            validated_on__isnull=False) and True or False

        if not(is_referent or is_admin):
            raise Http404()

        organisation = get_object_or_404(Organisation, id=id)
        instance = get_object_or_404(RemoteCsw, organisation=organisation)

        try:
            with transaction.atomic():
                instance.delete()
        except ValidationError as e:
            messages.error(request, e.__str__())
        except CswBaseError as e:
            messages.error(request, e.__str__())
        else:
            messages.success(request, (
                'Les informations ainsi que les jeux de données et '
                'ressources synchronisés avec le catalogue distant '
                'ont été supprimés avec succès.'))

        return HttpResponseRedirect(
            reverse('idgo_admin:update_organisation', kwargs={'id': organisation.id}))
