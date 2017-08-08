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
from mama_cas.cas import logout_user
from mama_cas.models import ServiceTicket
from mama_cas.utils import redirect as mama_redirect
from mama_cas.views import LoginView as MamaLoginView
from mama_cas.views import LogoutView as MamaLogoutView


def render_an_critical_error(request):
    # TODO(@m431m)
    message = ("Une erreur critique s'est produite lors de la création de "
               "votre compte. Merci de contacter l'administrateur du site. ")

    return render(request, 'idgo_admin/response.html',
                  {'message': message}, status=400)


@method_decorator([csrf_exempt], name='dispatch')
class SignIn(MamaLoginView):

    template_name = 'idgo_admin/signin.html'
    form_class = SignInForm

    # TODO: Vérifier si Profile pour l'utilisateur

    def form_valid(self, form):
        login(self.request, form.user)

        if form.cleaned_data.get('warn'):
            self.request.session['warn'] = True

        service = self.request.GET.get('service')
        if service:
            st = ServiceTicket.objects.create_ticket(
                service=service, user=self.request.user, primary=True)
            return mama_redirect(service, params={'ticket': st.ticket})

        nxt_pth = self.request.GET.get('next', None)
        if nxt_pth:
            return HttpResponseRedirect(nxt_pth)

        return redirect('idgo_admin:home')


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

        try:
            user = User.objects.create_user(
                username=data['username'], password=data['password'],
                email=data['email'], first_name=data['first_name'],
                last_name=data['last_name'],
                is_staff=False, is_superuser=False, is_active=False)
        except Exception as e:
            print('CreatingUserError', e)
            raise e

        try:
            profile = Profile.objects.create(user=user, role=data['role'],
                                             phone=data['phone'],
                                             rattachement_active=False,
                                             is_active=False)
        except Exception as e:
            print('CreatingProfileError', e)
            raise e

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
        # Demande de creation nouvelle organisation
        if created:
            AccountActions.objects.create(
                profile=profile, action="confirm_new_organisation")

        if organisation:
            # Demande de rattachement Profile-Organisation
            AccountActions.objects.create(
                profile=profile, action="confirm_rattachement",
                org_extras=organisation)

            # Demande de role de referent
            if data['referent_requested']:
                Liaisons_Referents.objects.create(
                    profile=profile, organisation=organisation)

            # Demande de role de contributeur
            if data['contribution_requested']:
                Liaisons_Contributeurs.objects.create(
                    profile=profile, organisation=organisation)

        signup_action = AccountActions.objects.create(profile=profile,
                                                      action="confirm_mail")
        try:
            Mail.validation_user_mail(request, signup_action)
        except Exception as e:
            print('SendingMailError', e)
            raise e

        try:
            ckan.add_user(user, data['password'])
            pass
        except Exception as e:
            # delete_user(user.username)  # TODO
            print('ExceptionCkan', e)
            raise e

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

    try:
        handle_new_profile(data)
    except IntegrityError:
        # uform.add_error('username',
        #                 'Cet identifiant de connexion est réservé.')
        return render_on_error()
    except Exception as e:
        print('ExceptionSignup', e)
        return render_an_critical_error(request)

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
        profile=profile, action='reset_password')
    if created is False:
        message = ('Un e-mail de réinitialisation à déjà été envoyé '
                   "Veuillez vérifier votre messagerie")
        return render(request, 'idgo_admin/message.html',
                      {'message': message}, status=200)

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
        return render(request, 'idgo_admin/resetpassword.html',
                      {'form': form})

    reset_action = get_object_or_404(
        AccountActions, key=key, action="reset_password")
    user = reset_action.profile.user

    error = False
    try:
        with transaction.atomic():
            user = form.save(request, user)
            pass
    except ValidationError as e:
        print('ValidationError', e)
        return render(request, 'idgo_admin/resetpassword.html',
                      {'form': form})
    except IntegrityError as e:
        print('IntegrityError', e)
        logout(request)
        error = True
    except Exception as e:
        print('Exception1', e)
        error = True
    if error:
        user = User.objects.get(username=user.username)
        try:
            ckan.update_user(user)
        except Exception as e:
            print('Exception', e)
        message = ('Erreur critique lors de la réinitialisation du '
                   'mot de passe. ')

        return render(request, 'idgo_admin/message.html',
                      {'message': message}, status=400)
    else:
        message = 'Votre mot de passe a été réinitialisé. '

        return render(request, 'idgo_admin/message.html',
                      {'message': message}, status=200)


@transaction.atomic
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def modify_account(request):

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
            profile=profile, action="confirm_rattachement",
            org_extras=organisation)

        try:
            Mail.confirm_updating_rattachement(request, rattachement_action)
        except Exception as e:
            print('SendingMailError', e)
            raise e

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
                profile=profile, action="confirm_contribution",
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
    pform = ProfileUpdateForm(
        request.POST or None, request.FILES, instance=profile,
        exclude={'user': user})

    if not uform.is_valid() or not pform.is_valid():
        return render(request, 'idgo_admin/modifyaccount.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'uform': uform, 'pform': pform})

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

    error = False
    try:
        with transaction.atomic():
            uform.save_f(request)
            profile = handle_update_profile(profile, data)
            # ckan.update_user(user, profile=profile)
    except ValidationError as e:
        print('ValidationError', e)
        return render(request, 'idgo_admin/modifyaccount.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'uform': uform,
                       'pform': pform})
    except IntegrityError as e:
        print('IntegrityError', e)
        logout(request)
        error = True
    except Exception as e:
        print('Exception', e)

    if error:
        user = User.objects.get(username=user.username)
        try:
            ckan.update_user(user)
        except Exception:
            pass
        render_an_critical_error(request)
    text = 'Les informations de votre profil sont à jour.'
    messages.success(request, text)
    return HttpResponseRedirect(reverse("idgo_admin:modifyAccount"))


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

    user_data_copy = {"last_name": user.last_name,
                      "first_name": user.first_name,
                      "username": user.username,
                      "email": user.email}
    user.delete()
    logout(request)
    try:
        Mail.conf_deleting_profile_to_user(user_data_copy)
    except Exception as e:
        print('Error', e)
        pass

    return render(request, 'idgo_admin/message.html',
                  context={'message': 'Votre compte a été supprimé.'},
                  status=200)
