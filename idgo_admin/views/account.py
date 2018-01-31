from datetime import datetime
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.account import ProfileForm
from idgo_admin.forms.account import SignInForm
from idgo_admin.forms.account import UserDeleteForm
from idgo_admin.forms.account import UserForgetPassword
from idgo_admin.forms.account import UserForm
from idgo_admin.forms.account import UserResetPassword
from idgo_admin.models import AccountActions
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import Mail
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile
from mama_cas.compat import is_authenticated as mama_is_authenticated
from mama_cas.models import ProxyGrantingTicket as MamaProxyGrantingTicket
from mama_cas.models import ProxyTicket as MamaProxyTicket
from mama_cas.models import ServiceTicket as MamaServiceTicket
from mama_cas.utils import redirect as mama_redirect
from mama_cas.utils import to_bool as mama_to_bool
from mama_cas.views import LoginView as MamaLoginView
from mama_cas.views import LogoutView as MamaLogoutView
import uuid


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators[0], name='dispatch')
class SignIn(MamaLoginView):

    template_name = 'idgo_admin/signin.html'
    form_class = SignInForm

    def get(self, request, *args, **kwargs):
        service = request.GET.get('service')
        gateway = mama_to_bool(request.GET.get('gateway'))
        if gateway and service:
            if mama_is_authenticated(request.user):
                st = MamaServiceTicket.objects.create_ticket(
                    service=service, user=request.user)
                if self.warn_user():
                    return mama_redirect('cas_warn', params={'service': service, 'ticket': st.ticket})
                return mama_redirect(service, params={'ticket': st.ticket})
            else:
                return mama_redirect(service)
        elif mama_is_authenticated(request.user):
            if service:
                st = MamaServiceTicket.objects.create_ticket(service=service, user=request.user)
                if self.warn_user():
                    return mama_redirect('cas_warn', params={'service': service, 'ticket': st.ticket})
                return mama_redirect(service, params={'ticket': st.ticket})
        return super(MamaLoginView, self).get(request, *args, **kwargs)

    def form_valid(self, form):
        login(self.request, form.user)

        if form.cleaned_data.get('warn'):
            self.request.session['warn'] = True

        service = self.request.GET.get('service')
        if service:
            st = MamaServiceTicket.objects.create_ticket(
                service=service, user=self.request.user, primary=True)
            return mama_redirect(service, params={'ticket': st.ticket})

        nxt_pth = self.request.GET.get('next', None)
        if nxt_pth:
            return HttpResponseRedirect(nxt_pth)

        return mama_redirect('idgo_admin:datasets')


def logout_user(request):
    if mama_is_authenticated(request.user):
        MamaServiceTicket.objects.consume_tickets(request.user)
        MamaProxyTicket.objects.consume_tickets(request.user)
        MamaProxyGrantingTicket.objects.consume_tickets(request.user)
        MamaServiceTicket.objects.request_sign_out(request.user)
        logout(request)


class SignOut(MamaLogoutView):

    def get(self, request, *args, **kwargs):

        service = request.GET.get('service')
        if not service:
            service = request.GET.get('url')
        follow_url = getattr(settings, 'MAMA_CAS_FOLLOW_LOGOUT_URL', True)
        logout_user(request)
        if service and follow_url:
            return mama_redirect(service)
        return mama_redirect('idgo_admin:signIn')


@method_decorator(decorators[0], name='dispatch')
class AccountManager(View):

    def create_account(self, user_data, profile_data):
        user = User.objects.create_user(
            username=user_data['username'], password=user_data['password1'],
            email=user_data['email'], first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            is_staff=False, is_superuser=False, is_active=False)

        profile = Profile.objects.create(
            user=user, phone=profile_data['phone'],
            membership=False, is_active=False)

        return user, profile

    def handle_me(self, request, user_data, profile_data, user, profile, process):

        if process in ("update", "update_organization"):
            user.first_name = user_data['first_name']
            user.last_name = user_data['last_name']
            user.username = user_data['username']

            password = user_data.get('password1', None)
            if password:
                user.set_password(password)
                user.save()
                logout(request)
                login(request, user,
                      backend='django.contrib.auth.backends.ModelBackend')
            user.save()

            if profile_data['phone']:
                profile.phone = profile_data['phone']

        if profile_data['mode'] == 'nothing_to_do':
            profile.save()
            return user, profile, None, False

        if profile_data['mode'] == 'no_organization_please':  # TODO?
            profile.save()
            return user, profile, None, False

        if profile_data['mode'] == 'change_organization':
            organisation = profile_data['organisation']
            org_created = False

        if profile_data['mode'] == 'require_new_organization':
            organisation, org_created = \
                Organisation.objects.get_or_create(
                    name=profile_data['new_orga'],
                    defaults={
                        'address': profile_data['address'],
                        'city': profile_data['city'],
                        # 'code_insee': profile_data['code_insee'],
                        'postcode': profile_data['postcode'],
                        'description': profile_data['description'],
                        'financier': profile_data['financier'],
                        'jurisdiction': profile_data['jurisdiction'],
                        'license': profile_data['license'],
                        'logo': profile_data['logo'],
                        'organisation_type': profile_data['organisation_type'],
                        # 'parent': profile_data['parent'],
                        # 'status': profile_data['status'],
                        'website': profile_data['website'],
                        'is_active': False})

        profile.organisation = organisation
        profile.membership = False
        profile.save()
        return user, profile, organisation, org_created

    def signup_process(self, request, profile):
        signup_action = AccountActions.objects.create(profile=profile,
                                                      action="confirm_mail")
        Mail.validation_user_mail(request, signup_action)

    def new_org_process(self, request, profile, process):
        # Ajout clé uuid et envoi mail aux admin pour confirmations de création
        new_organisation_action = AccountActions.objects.create(
            profile=profile, action='confirm_new_organisation')
        if process in ("update", "update_organization"):
            Mail.confirm_new_organisation(request, new_organisation_action)

    def rattachement_process(self, request, profile, organisation, process):
        # Demande de rattachement à l'organisation
        rattachement_action = AccountActions.objects.create(
            profile=profile, action='confirm_rattachement',
            org_extras=organisation)
        if process in ("update", "update_organization"):
            Mail.confirm_updating_rattachement(request, rattachement_action)

    def referent_process(self, request, profile, organisation, process):
        LiaisonsReferents.objects.get_or_create(
            profile=profile, organisation=organisation, validated_on=None)
        if process in ("update", "update_organization"):
            referent_action = AccountActions.objects.create(
                profile=profile, action='confirm_referent',
                org_extras=organisation)
            Mail.confirm_referent(request, referent_action)
        # Un referent est obligatoirement un contributeur
        self.contributor_process(request, profile, organisation, process, send_mail=False)

    def contributor_process(self, request, profile, organisation, process, send_mail=True):
        LiaisonsContributeurs.objects.get_or_create(
            profile=profile, organisation=organisation)
        if process in ("update", "update_organization") and send_mail:
            contribution_action = AccountActions.objects.create(
                profile=profile, action='confirm_contribution',
                org_extras=organisation)
            Mail.confirm_contribution(request, contribution_action)

    def contextual_response(self, request, process):
        if process == "create":
            message = ('Votre compte a bien été créé. Vous recevrez un e-mail '
                       "de confirmation d'ici quelques minutes. Pour activer "
                       'votre compte, cliquez sur le lien qui vous sera indiqué '
                       "dans les 48h après réception de l'e-mail.")

            return render(request, 'idgo_admin/message.html',
                          {'message': message}, status=200)

        if process == "update_organization":
            messages.success(
                request, 'Les informations de votre profil sont à jour.')
            name_space = 'idgo_admin:my_organization'

        if process == "update":
            messages.success(
                request, 'Les informations de votre profil sont à jour.')
            name_space = 'idgo_admin:account_manager'

        return HttpResponseRedirect(reverse(name_space,
                                            kwargs={'process': process}))

    def contextual_template(self, process):
        return {'create': 'idgo_admin/signup.html',
                'update': 'idgo_admin/modifyaccount.html',
                'update_organization': 'idgo_admin/update_my_organization.html'}.get(process)

    def render_on_error(self, request, html_template, uform, pform):
        return render(request, html_template,
                      {'uform': uform, 'pform': pform})

    def rewind_ckan(self, username):
        ckan.update_user(User.objects.get(username=username))

    def get(self, request, process):

        if process == "create":
            return render(
                request, self.contextual_template(process),
                {'uform': UserForm(include={'action': process}),
                 'pform': ProfileForm(include={'action': process})})

        elif process in ("update", "update_organization"):

            try:
                user, profile = user_and_profile(request)
            except ProfileHttp404:
                return HttpResponseRedirect(reverse('idgo_admin:signIn'))

            return render_with_info_profile(
                request, self.contextual_template(process),
                {'uform': UserForm(instance=user, include={'action': process}),
                 'pform': ProfileForm(instance=profile, include={'user': user, 'action': process})})

    @transaction.atomic
    def post(self, request, process):

        if process == "create":
            pform = ProfileForm(request.POST, request.FILES,
                                include={'action': process})
            uform = UserForm(data=request.POST, include={'action': process})

        if process in ("update", "update_organization"):

            try:
                user, profile = user_and_profile(request)
            except ProfileHttp404:
                return HttpResponseRedirect(reverse('idgo_admin:signIn'))

            pform = ProfileForm(request.POST, request.FILES,
                                instance=profile,
                                include={'user': user,
                                         'action': process})
            uform = UserForm(data=request.POST, instance=user, include={'action': process})

        if not uform.is_valid() or not pform.is_valid():
            if process == "create":
                return render(
                    request, self.contextual_template(process),
                    {'uform': uform, 'pform': pform})
            if process in ("update", "update_organization"):
                return render_with_info_profile(
                    request, self.contextual_template(process),
                    {'uform': uform, 'pform': pform})

        if process == "create":
            if ckan.is_user_exists(uform.cleaned_data['username']):
                uform.add_error('username',
                                'Cet identifiant de connexion est réservé.')
                return self.render_on_error(
                    request, self.contextual_template(process), uform, pform)

            user, profile = self.create_account(uform.cleaned_data,
                                                pform.cleaned_data)

        try:
            with transaction.atomic():
                user, profile, organisation, org_created = self.handle_me(
                    request,
                    uform.cleaned_data,
                    pform.cleaned_data, user, profile, process)
                if process in ("update", "update_organization"):
                    ckan.update_user(user)

        except ValidationError as e:
            if process in ("update", "update_organization"):
                ckan.update_user(User.objects.get(username=user.username))
                return render_with_info_profile(
                    request, self.contextual_template(process),
                    {'uform': uform, 'pform': pform})
            raise e

        except Exception as e:
            if process in ("update", "update_organization"):
                ckan.update_user(User.objects.get(username=user.username))
                messages.error(
                    request, 'Une erreur est survenue lors de la modification de votre compte.')
            raise e

        else:
            if org_created:
                self.new_org_process(request, profile, process)
            if pform.cleaned_data['mode'] in ['change_organization', 'require_new_organization']:
                self.rattachement_process(request, profile, organisation, process)
                if pform.cleaned_data.get('referent_requested'):
                    self.referent_process(request, profile, organisation, process)
                if pform.cleaned_data.get('contribution_requested'):
                    self.contributor_process(request, profile, organisation, process)
            if process == "create":
                ckan.add_user(user, uform.cleaned_data['password1'])
                self.signup_process(request, profile)
            return self.contextual_response(request, process)


@csrf_exempt
def forgotten_password(request):

    if request.method == 'GET':
        return render(request, 'idgo_admin/forgottenpassword.html',
                      {'form': UserForgetPassword()})

    form = UserForgetPassword(data=request.POST)

    if not form.is_valid():
        return render(request, 'idgo_admin/forgottenpassword.html',
                      {'form': form})
    try:
        profile = Profile.objects.get(
            user__email=form.cleaned_data["email"], is_active=True)
    except Exception:
        message = "Cette adresse n'est pas liée a un compte IDGO actif "
        return render(request, 'idgo_admin/message.html',
                      {'message': message}, status=200)

    action, created = AccountActions.objects.get_or_create(
        profile=profile, action='reset_password', closed=None)

    try:
        Mail.send_reset_password_link_to_user(request, action)
    except Exception as e:
        message = ("Une erreur s'est produite lors de l'envoi du mail "
                   "de réinitialisation: {error}".format(error=e))

        status = 400
    else:
        message = ('Vous recevrez un e-mail de réinitialisation '
                   "de mot de passe d'ici quelques minutes. "
                   'Pour changer votre mot de passe, '
                   'cliquez sur le lien qui vous sera indiqué '
                   "dans les 48h après réception de l'e-mail.")
        status = 200
    finally:
        return render(request, 'idgo_admin/message.html',
                      {'message': message}, status=status)


@transaction.atomic
@csrf_exempt
def reset_password(request, key):

    if request.method == 'GET':
        return render(request, 'idgo_admin/resetpassword.html',
                      {'form': UserResetPassword()})

    form = UserResetPassword(data=request.POST)
    if not form.is_valid():
        return render(request, 'idgo_admin/resetpassword.html', {'form': form})

    try:
        uuid.UUID(key)
    except Exception:
        raise Http404

    try:
        reset_action = AccountActions.objects.get(
            key=key, action="reset_password",
            profile__user__username=form.cleaned_data.get('username'))
    except Exception:
        message = ("Une erreur s'est produite lors de la "
                   'réinitialisation de votre mot de passe')

        status = 400
        return render(request, 'idgo_admin/message.html',
                      {'message': message}, status=status)

    user = reset_action.profile.user
    try:
        with transaction.atomic():
            user = form.save(request, user)
            reset_action.closed = datetime.now()
            reset_action.save()
    except ValidationError:
        return render(request, 'idgo_admin/resetpassword.html', {'form': form})
    except IntegrityError:
        logout(request)
    except Exception:
        messages.error(
            request, 'Une erreur est survenue lors de la modification de votre compte.')
    else:
        messages.success(
            request, 'Votre mot de passe a été réinitialisé.')

    return HttpResponseRedirect(
        reverse('idgo_admin:account_manager', kwargs={'process': 'update'}))


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def delete_account(request):

    user = request.user
    if request.method == 'GET':
        return render_with_info_profile(
            request, 'idgo_admin/deleteaccount.html',
            {'uform': UserDeleteForm()})

    uform = UserDeleteForm(data=request.POST)
    if not uform.is_valid():
        return render_with_info_profile(
            request, 'idgo_admin/deleteaccount.html', {'uform': uform})

    user_data_copy = {'last_name': user.last_name,
                      'first_name': user.first_name,
                      'username': user.username,
                      'email': user.email}
    logout(request)
    user.delete()

    Mail.conf_deleting_profile_to_user(user_data_copy)

    return render(request, 'idgo_admin/message.html', status=200,
                  context={'message': 'Votre compte a été supprimé.'})


@method_decorator(decorators, name='dispatch')
class ReferentAccountManager(View):

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):

        user, profile = user_and_profile(request)

        if not profile.referents.exists() and not profile.is_admin:
            raise Http404

        my_subordinates = profile.is_admin and Organisation.objects.filter(is_active=True) or LiaisonsReferents.get_subordinated_organizations(profile=profile)

        organizations = {}
        for orga in my_subordinates:
            organizations[str(orga.name)] = {'id': orga.id}
            organizations[str(orga.name)]["members"] = [{
                "profile_id": p.pk,
                "is_referent": p.get_roles(organisation=orga)["is_referent"] and "true" or "false",
                "first_name": p.user.first_name,
                "last_name": p.user.last_name,
                "username": p.user.username,
                "nb_datasets": p.nb_datasets(orga)
                } for p in Profile.objects.filter(organisation=orga, membership=True).order_by('user__last_name')]

            organizations[str(orga.name)]["contributors"] = [{
                "profile_id": lc.profile.pk,
                "is_referent": lc.profile.get_roles(organisation=orga)["is_referent"] and "true" or "false",
                "first_name": lc.profile.user.first_name,
                "last_name": lc.profile.user.last_name,
                "username": lc.profile.user.username,
                "nb_datasets": lc.profile.nb_datasets(orga)
                } for lc in LiaisonsContributeurs.objects.filter(
                organisation=orga, validated_on__isnull=False).order_by('profile__user__last_name')]

        return render_with_info_profile(
            request, 'idgo_admin/all_members.html', status=200,
            context={'organizations': organizations})

    def delete(self, request, *args, **kwargs):

        organization_id = request.GET.get('organization')
        username = request.GET.get('username')
        target = request.GET.get('target')
        if not organization_id or not username or target not in ['members', 'contributors']:
            raise Http404

        profile = get_object_or_404(Profile, user__username=username)
        organisation = get_object_or_404(Organisation, id=organization_id)
        if profile.get_roles(organisation=organisation)["is_referent"]:
            return HttpResponseForbidden()

        if target == 'members':
            if profile.organisation != organisation:
                raise Http404

            profile.organisation = None
            profile.membership = False
            profile.save()
            message = "L'utilisateur <strong>{0}</strong> n'est plus membre de cette organidation. ".format(username)
            messages.success(request, message)

        if target == 'contributors':
            lc = get_object_or_404(LiaisonsContributeurs, profile=profile, organisation=organisation)
            lc.delete()
            message = "L'utilisateur <strong>{0}</strong> n'est plus contributeur de cette organisation. ".format(username)
            messages.success(request, message)

        return HttpResponse(status=200)
