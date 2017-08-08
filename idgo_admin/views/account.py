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
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.forms.account import ProfileUpdateForm
from idgo_admin.forms.account import SignInForm
from idgo_admin.forms.account import UserDeleteForm
from idgo_admin.forms.account import UserForgetPassword
from idgo_admin.forms.account import UserForm
from idgo_admin.forms.account import UserProfileForm
from idgo_admin.forms.account import UserResetPassword
from idgo_admin.forms.account import UserUpdateForm
from idgo_admin.models import AccountActions
from idgo_admin.models import Liaisons_Contributeurs
from idgo_admin.models import Liaisons_Referents
from idgo_admin.models import Mail
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from mama_cas.compat import is_authenticated as mama_is_authenticated
from mama_cas.models import ProxyGrantingTicket as MamaProxyGrantingTicket
from mama_cas.models import ProxyTicket as MamaProxyTicket
from mama_cas.models import ServiceTicket as MamaServiceTicket
from mama_cas.utils import redirect as mama_redirect
from mama_cas.utils import to_bool as mama_to_bool
from mama_cas.views import LoginView as MamaLoginView
from mama_cas.views import LogoutView as MamaLogoutView


@method_decorator([csrf_exempt], name='dispatch')
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
        return super().get(request, *args, **kwargs)

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

        return mama_redirect('idgo_admin:home')


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
            return redirect(service)
        return redirect('idgo_admin:signIn')


@csrf_exempt
def sign_up(request):

    if request.method == 'GET':
        return render(request, 'idgo_admin/signup.html',
                      {'uform': UserForm(), 'pform': UserProfileForm()})

    def handle_new_profile(data):

        user = User.objects.create_user(
            username=data['username'], password=data['password'],
            email=data['email'], first_name=data['first_name'],
            last_name=data['last_name'],
            is_staff=False, is_superuser=False, is_active=False)

        profile = Profile.objects.create(
            user=user, role=data['role'], phone=data['phone'],
            rattachement_active=False, is_active=False)

        # Si rattachement à nouvelle organisation requis
        name = data['new_orga']
        created = False
        organisation = None
        if data['is_new_orga'] and name:
            organisation, created = Organisation.objects.get_or_create(
                name=name,
                defaults={
                    'adresse': data['adresse'],
                    'code_insee': data['code_insee'],
                    'code_postal': data['code_postal'],
                    'description': data['description'],
                    'financeur': data['financeur'],
                    'license': data['license'],
                    'logo': data['logo'],
                    'organisation_type': data['organisation_type'],
                    # 'parent': data['parent'],
                    'status': data['status'],
                    'ville': data['ville'],
                    'website': data['website'],
                    'is_active': False})
        elif data['is_new_orga'] is False and data['organisation']:
            organisation = data['organisation']

        profile.organisation = organisation
        profile.rattachement_active = False
        profile.save()

        # Demande de création d'une nouvelle organisation
        if created:
            AccountActions.objects.create(
                profile=profile, action="confirm_new_organisation")

        # Demande de rattachement (Profile-Organisation)
        if organisation:
            AccountActions.objects.create(
                profile=profile, action="confirm_rattachement",
                org_extras=organisation)

            # Demande de rôle de referent
            if data['referent_requested']:
                Liaisons_Referents.objects.create(
                    profile=profile, organisation=organisation)

            # Demande de rôle de contributeur
            if data['contribution_requested']:
                Liaisons_Contributeurs.objects.create(
                    profile=profile, organisation=organisation)

        signup_action = AccountActions.objects.create(profile=profile,
                                                      action="confirm_mail")

        Mail.validation_user_mail(request, signup_action)
        ckan.add_user(user, data['password'])

    def delete_user(username):
        User.objects.get(username=username).delete()

    def render_on_error():
        return render(request, 'idgo_admin/signup.html',
                      {'uform': uform, 'pform': pform})

    uform = UserForm(data=request.POST)
    pform = UserProfileForm(request.POST, request.FILES)

    if not uform.is_valid() or not pform.is_valid():
        return render_on_error()

    if uform.cleaned_data['password1'] != uform.cleaned_data['password2']:
        uform.add_error('password1', 'Vérifiez les champs mot de passe')
        return render_on_error()

    if uform.cleaned_data["email"] and \
            User.objects.filter(
                email=uform.cleaned_data["email"]).count() > 0:
        uform.add_error('email', 'Cette adresse e-mail est réservée.')
        return render_on_error()

    data = {
        'username': uform.cleaned_data['username'],
        'email': uform.cleaned_data['email'],
        'password': uform.cleaned_data['password1'],
        'first_name': uform.cleaned_data['first_name'],
        'last_name': uform.cleaned_data['last_name'],
        'role': pform.cleaned_data['role'],
        'phone': pform.cleaned_data['phone'],
        'organisation': pform.cleaned_data['organisation'],
        'new_orga': pform.cleaned_data['new_orga'],
        'logo': pform.cleaned_data['logo'],
        'parent': pform.cleaned_data['parent'],
        'organisation_type': pform.cleaned_data['organisation_type'],
        'code_insee': pform.cleaned_data['code_insee'],
        'description': pform.cleaned_data['description'],
        'adresse': pform.cleaned_data['adresse'],
        'code_postal': pform.cleaned_data['code_postal'],
        'ville': pform.cleaned_data['ville'],
        'org_phone': pform.cleaned_data['org_phone'],
        'financeur': pform.cleaned_data['financeur'],
        'status': pform.cleaned_data['status'],
        'license': pform.cleaned_data['license'],
        'website': pform.cleaned_data['website'],
        'referent_requested': pform.cleaned_data['referent_requested'],
        'contribution_requested': pform.cleaned_data['contribution_requested'],
        'is_new_orga': pform.cleaned_data['is_new_orga']}

    if ckan.is_user_exists(data['username']):
        uform.add_error('username',
                        'Cet identifiant de connexion est réservé.')
        return render_on_error()

    handle_new_profile(data)

    message = ('Votre compte a bien été créé. Vous recevrez un e-mail '
               "de confirmation d'ici quelques minutes. Pour activer "
               'votre compte, cliquez sur le lien qui vous sera indiqué '
               "dans les 48h après réception de l'e-mail.")

    return render(request, 'idgo_admin/message.html',
                  {'message': message}, status=200)


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

    reset_action = \
        get_object_or_404(AccountActions, key=key, action="reset_password")

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

    return HttpResponseRedirect(reverse('idgo_admin:modifyAccount'))


@transaction.atomic
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def modify_account(request):

    def rewind_ckan():
        ckan.update_user(User.objects.get(username=user.username))

    def handle_update_profile(profile, data):

        if data['role']:
            profile.role = data['role']
        if data['phone']:
            profile.phone = data['phone']

        if data['mode'] == 'nothing_to_do':
            profile.save()
            return profile

        if data['mode'] == 'no_organization_please':  # TODO?
            profile.save()
            return profile

        if data['mode'] == 'change_organization':
            organisation = data['organisation']
            created = False

        if data['mode'] == 'require_new_organization':
            organisation, created = \
                Organisation.objects.get_or_create(
                    name=data['new_orga'],
                    defaults={
                        'adresse': data['adresse'],
                        'code_insee': data['code_insee'],
                        'code_postal': data['code_postal'],
                        'description': data['description'],
                        'financeur': data['financeur'],
                        'license': data['license'],
                        'logo': data['logo'],
                        'organisation_type': data['organisation_type'],
                        # 'parent': data['parent'],
                        'status': data['status'],
                        'ville': data['ville'],
                        'website': data['website'],
                        'is_active': False})

        profile.organisation = organisation
        profile.rattachement_active = False
        profile.save()

        if created:
            # Ajout d'une clé de création de l'organisation
            new_organisation_action = AccountActions.objects.create(
                profile=profile, action='confirm_new_organisation')
            try:
                Mail.confirm_new_organisation(request, new_organisation_action)
            except Exception as e:
                print('SendingMailError', e)
                raise e

        # Demande de rattachement à l'organisation
        rattachement_action = AccountActions.objects.create(
            profile=profile, action='confirm_rattachement',
            org_extras=organisation)

        Mail.confirm_updating_rattachement(request, rattachement_action)

        # Demande de rôle de référent
        if data['referent_requested']:
            Liaisons_Referents.objects.get_or_create(
                profile=profile, organisation=organisation)
            referent_action = AccountActions.objects.create(
                profile=profile, action='confirm_referent',
                org_extras=organisation)
            try:
                Mail.confirm_referent(request, referent_action)
            except Exception as e:
                print('SendingMailError', e)
                raise e

        # Demande de rôle de contributeur
        if data['contribution_requested']:
            Liaisons_Contributeurs.objects.get_or_create(
                profile=profile, organisation=organisation)
            contribution_action = AccountActions.objects.create(
                profile=profile, action='confirm_contribution',
                org_extras=organisation)
            try:
                Mail.confirm_contribution(request, contribution_action)
            except Exception as e:
                print('SendingMailError', e)
                raise e

        profile.save()
        return profile

    # END OF handle_update_profile()

    user = request.user
    profile = get_object_or_404(Profile, user=user)

    if request.method == 'GET':
        return render(request, 'idgo_admin/modifyaccount.html',
                      {'uform': UserUpdateForm(instance=user),
                       'pform': ProfileUpdateForm(instance=profile,
                                                  exclude={'user': user})})

    uform = UserUpdateForm(instance=user, data=request.POST or None)
    pform = ProfileUpdateForm(request.POST or None, request.FILES,
                              instance=profile, exclude={'user': user})

    if not uform.is_valid() or not pform.is_valid():
        return render(request, 'idgo_admin/modifyaccount.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'uform': uform,
                       'pform': pform})

    data = {
        'mode': pform.cleaned_data['mode'],
        'username': uform.cleaned_data['username'],
        'email': uform.cleaned_data['email'],
        'password': uform.cleaned_data['password1'],
        'first_name': uform.cleaned_data['first_name'],
        'last_name': uform.cleaned_data['last_name'],
        'role': pform.cleaned_data['role'],
        'phone': pform.cleaned_data['phone'],
        'organisation': pform.cleaned_data['organisation'],
        'new_orga': pform.cleaned_data['new_orga'],
        'logo': pform.cleaned_data['logo'],
        'parent': pform.cleaned_data['parent'],
        'organisation_type': pform.cleaned_data['organisation_type'],
        'code_insee': pform.cleaned_data['code_insee'],
        'description': pform.cleaned_data['description'],
        'adresse': pform.cleaned_data['adresse'],
        'code_postal': pform.cleaned_data['code_postal'],
        'ville': pform.cleaned_data['ville'],
        'org_phone': pform.cleaned_data['org_phone'],
        'financeur': pform.cleaned_data['financeur'],
        'status': pform.cleaned_data['status'],
        'license': pform.cleaned_data['license'],
        'website': pform.cleaned_data['website'],
        'referent_requested': pform.cleaned_data['referent_requested'],
        'contribution_requested': pform.cleaned_data['contribution_requested'],
        'is_new_orga': pform.cleaned_data['is_new_orga']}

    try:
        with transaction.atomic():
            uform.save_f(request)
            profile = handle_update_profile(profile, data)
            ckan.update_user(user)
    except ValidationError:
        rewind_ckan()
        return render(request, 'idgo_admin/modifyaccount.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'uform': uform,
                       'pform': pform})
    except Exception:
        rewind_ckan()
        messages.error(
            request, 'Une erreur est survenue lors de la modification de votre compte.')
    else:
        messages.success(
            request, 'Les informations de votre profil sont à jour.')

    return HttpResponseRedirect(reverse('idgo_admin:modifyAccount'))


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def delete_account(request):

    user = request.user
    if request.method == 'GET':
        return render(request, 'idgo_admin/deleteaccount.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'uform': UserDeleteForm()})

    user = request.user
    uform = UserDeleteForm(data=request.POST)
    if not uform.is_valid():
        return render(request, 'idgo_admin/deleteaccount.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'uform': uform})

    user_data_copy = {'last_name': user.last_name,
                      'first_name': user.first_name,
                      'username': user.username,
                      'email': user.email}
    logout(request)
    user.delete()

    Mail.conf_deleting_profile_to_user(user_data_copy)

    return render(request, 'idgo_admin/message.html',
                  context={'message': 'Votre compte a été supprimé.'},
                  status=200)
