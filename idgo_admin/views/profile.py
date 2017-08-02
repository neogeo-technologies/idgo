from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
# from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.forms.profile import LiaisonsDeleteForm
from idgo_admin.forms.profile import ProfileUpdateForm
from idgo_admin.forms.profile import UserDeleteForm
from idgo_admin.forms.profile import UserForgetPassword
from idgo_admin.forms.profile import UserForm
# from idgo_admin.forms.profile import UserLoginForm
from idgo_admin.forms.profile import UserProfileForm
from idgo_admin.forms.profile import UserResetPassword
from idgo_admin.forms.profile import UserUpdateForm
from idgo_admin.models import AccountActions
from idgo_admin.models import Dataset
from idgo_admin.models import Financeur
from idgo_admin.models import Liaisons_Contributeurs
from idgo_admin.models import Liaisons_Referents
from idgo_admin.models import License
from idgo_admin.models import Mail
from idgo_admin.models import Organisation
from idgo_admin.models import OrganisationType
from idgo_admin.models import Profile
from idgo_admin.models import Status
import json
from mama_cas.cas import logout_user
# from mama_cas.compat import is_authenticated
from mama_cas.models import ServiceTicket
# from mama_cas.utils import to_bool
from mama_cas.utils import redirect as mama_redirect
from mama_cas.views import LoginView
from mama_cas.views import LogoutView



def render_an_critical_error(request, error=None):
    # TODO(@m431m)
    message = ("Une erreur critique s'est produite lors de la création de "
               "votre compte. Merci de contacter l'administrateur du site: {error} ").format(
                        error=error)

    return render(request, 'idgo_admin/response.html',
                  {'message': message}, status=400)


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


class SignIn(LoginView):

    template_name = 'idgo_admin/signin.html'

    def form_valid(self, form):
        login(self.request, form.user)

        if form.cleaned_data.get('warn'):
            self.request.session['warn'] = True

        service = self.request.GET.get('service')
        if service:
            st = ServiceTicket.objects.create_ticket(
                service=service, user=self.request.user, primary=True)
            return mama_redirect(service, params={'ticket': st.ticket})
        return redirect('idgo_admin:home')


class SignOut(LogoutView):

    def get(self, request, *args, **kwargs):

        service = request.GET.get('service')
        if not service:
            service = request.GET.get('url')
        follow_url = getattr(settings, 'MAMA_CAS_FOLLOW_LOGOUT_URL', True)
        logout_user(request)
        if service and follow_url:
            return redirect(service)
        # return redirect('cas_login')
        return redirect('idgo_admin:signIn')


# @csrf_exempt
# def sign_out(request):
#     logout(request)
#     return redirect('idgo_admin:signIn')


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
        name = None
        if data['is_new_orga']:
            if Organisation.objects.filter(name=data['new_orga']):
                raise IntegrityError
            else:
                name = data['new_orga']
        elif data['is_new_orga'] is False and data['organisation']:
            name = data['organisation'].name

        if name:
            try:
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
            except Exception as e:
                print('CreatingOrganisationError', e)
                raise e
            # rattachement nouvelle organisation
            profile.organisation = organisation
            profile.save()
            # Demande de creation nouvelle organisation
            if created:
                AccountActions.objects.create(
                    profile=profile, action="confirm_new_organisation")

        if name:
            # Demande de rattachement Profile-Organisation
            AccountActions.objects.create(
                profile=profile, action="confirm_rattachement")

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
        return render_an_critical_error(request, e)

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
    except:
        message = "Cette adresse n'est pas liée a un compte IDGO actif "
        return render(request, 'idgo_admin/message.html',
                      {'message': message}, status=200)

    action, created = AccountActions.objects.get_or_create(profile=profile, action='reset_password')
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
            # TODO(@cbenhabib) MAJ MDP: a voir en fonction du SSO
            # CF save de UserResetPassword
            # user = form.save(request, user)
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
        message = 'Erreur critique lors de la réinitialisation du mot de passe.'

        return render(request, 'idgo_admin/message.html',
                      {'message': message}, status=400)
    else:
        message = 'Votre mot de passe a été réinitialisé. '

        return render(request, 'idgo_admin/message.html',
                      {'message': message}, status=200)


@csrf_exempt
def confirmation_mail(request, key):

    # confirmation de l'email par l'utilisateur
    action = get_object_or_404(AccountActions, key=key, action='confirm_mail')
    if action.closed:
        message = "Vous avez déjà validé votre adresse e-mail."
        return render(request, 'idgo_admin/message.html',
                      {'message': message}, status=200)

    user = action.profile.user
    profile = action.profile
    organisation = action.profile.organisation

    user.is_active = True
    action.profile.is_active = True
    try:
        ckan.activate_user(user.username)
    except Exception as e:
        print('Exception', e.__str__)
        return render_an_critical_error(request)
    user.save()
    action.profile.save()
    if organisation:
        # Demande de creation nouvelle organisation
        if organisation.is_active is False:
            new_organisation_action = AccountActions.objects.get(
                profile=profile, action="confirm_new_organisation")
            try:
                Mail.confirm_new_organisation(request, new_organisation_action)
            except Exception as e:
                print('SendingMailError', e.__str__)
                raise e

        # Demande de rattachement Profile-Organsaition
        rattachement_action = AccountActions.objects.get(
            profile=profile, action="confirm_rattachement")
        try:
            Mail.confirm_rattachement(request, rattachement_action)
        except Exception as e:
            print('SendingMailError', e.__str__)
            raise e

        # Demande de role de referent
        try:
            Liaisons_Referents.objects.get(
                profile=profile, organisation=organisation)
        except Exception as e:
            pass
        else:
            referent_action = AccountActions.objects.create(
                profile=profile, action='confirm_referent',
                org_extras=organisation)
            try:
                Mail.confirm_referent(request, referent_action)
            except Exception as e:
                print('SendingMailError', e.__str__)
                raise e

        # Demande de role de contributeur
        try:
            Liaisons_Contributeurs.objects.get(
                profile=profile, organisation=organisation)
        except Exception as e:
            pass
        else:
            contribution_action = AccountActions.objects.create(
                profile=profile, action="confirm_contribution",
                org_extras=organisation)
            try:
                Mail.confirm_contribution(request, contribution_action)
            except Exception as e:
                print('SendingMailError', e.__str__)
                raise e

    try:
        Mail.confirmation_user_mail(user)
    except Exception:
        pass  # Ce n'est pas très grave si l'e-mail ne part pas...

    action.closed = timezone.now()
    action.save()
    message = ("Merci d'avoir confirmer votre adresse e-mail. "
               'Toute demande de rattachement, contribution, '
               'ou rôle de référent pour une organisation, '
               "ne sera effective qu'après validation par un administrateur.")

    return render(request, 'idgo_admin/message.html',
                  {'message': message}, status=200)


@csrf_exempt
def confirm_new_orga(request, key):

    action = get_object_or_404(
        AccountActions, key=key, action='confirm_new_organisation')

    name = action.profile.organisation.name
    if action.closed:
        message = \
            "La création de l'organisation {0} a déjà été confirmée.".format(name)

    else:
        action.profile.organisation.is_active = True
        action.profile.organisation.save()
        ckan.add_organization(action.profile.organisation)  # TODO: A la création du premier dataset
        action.closed = timezone.now()
        action.save()
        message = ("L'organisation {0} a bien été créee. "
                   "Des utilisateurs peuvent désormais y etre rattaché, "
                   "demander à en etre contributeur ou référent ").format(name)

    return render(request, 'idgo_admin/message.html',
                  {'message': message}, status=200)


@csrf_exempt
def confirm_rattachement(request, key):

    action = get_object_or_404(
        AccountActions, key=key, action='confirm_rattachement')

    if action.closed:
        action.profile.rattachement_active = True
        action.profile.save()
        name = action.org_extras.name
        user = action.profile.user
        message = (
            "Le rattachement de {first_name} {last_name} ({username}) "
            "à l'organisation {organization_name} a déjà été confirmée."
            ).format(first_name=user.first_name,
                     last_name=user.last_name,
                     username=user.username,
                     organization_name=name)
    else:
        action.profile.rattachement_active = True
        name = action.org_extras.name
        action.closed = timezone.now()
        user = action.profile.user
        action.profile.save()
        action.save()

        message = (
            "Le rattachement de {first_name} {last_name} ({username}) "
            "à l'organisation {organization_name} a bien été confirmée."
            ).format(first_name=user.first_name,
                     last_name=user.last_name,
                     username=user.username,
                     organization_name=name)

    return render(request, 'idgo_admin/message.html',
                  {'message': message}, status=200)


@csrf_exempt
def confirm_referent(request, key):

    action = get_object_or_404(
        AccountActions, key=key, action='confirm_referent')

    organisation = action.org_extras
    if action.closed:
        status = 200
        message = (
            "Le rôle de référent de l'organisation {organization_name} "
            "a déjà été confirmée pour <strong>{username}</strong>."
            ).format(organization_name=organisation.name,
                     username=action.profile.username)
    else:
        try:
            ref_liaison = Liaisons_Referents.objects.get(
                profile=action.profile, organisation=organisation)
        except Exception:
            status = 400
            message = ("Erreur lors de la validation du role de réferent")
        else:
            ref_liaison.validated_on = timezone.now()
            ref_liaison.save()
            action.closed = timezone.now()
            action.save()

            status = 200
            message = (
                "Le rôle de référent de l'organisation {organization_name} "
                "a bien été confirmée pour <strong>{username}</strong>."
                ).format(organization_name=organisation.name,
                         username=action.profile.username)

    return render(request, 'idgo_admin/message.html',
                  {'message': message}, status=status)


@csrf_exempt
def confirm_contribution(request, key):

    action = get_object_or_404(
        AccountActions, key=key, action='confirm_contribution')
    organisation = action.org_extras

    if action.closed:
        message = (
            "Le rôle de contributeur pour l'organisation {organization_name} "
            "a déjà été confirmée pour <strong>{username}</strong>."
            ).format(organization_name=organisation.name,
                     username=action.profile.username)
        status = 200

    else:
        try:
            contrib_liaison = Liaisons_Contributeurs.objects.get(
                profile=action.profile, organisation=organisation)
        except:
            message = ("Erreur lors de la validation du rôle de contributeur")
            status = 400

        else:
            user = action.profile.user
            ckan.add_user_to_organization(
                user.username, organisation.ckan_slug, role='editor')
            contrib_liaison.validated_on = timezone.now()
            contrib_liaison.save()
            action.closed = timezone.now()
            action.save()

            status = 200
            message = (
                "Le rôle de contributeur pour l'organisation {organization_name} "
                "a bien été confirmée pour <strong>{username}</strong>."
                ).format(organization_name=organisation.name,
                         username=user.username)
            try:
                Mail.confirm_contrib_to_user(action)
            except Exception:
                pass

    return render(request, 'idgo_admin/message.html',
                  {'message': message}, status=status)


@transaction.atomic
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def modify_account(request):

    def handle_update_profile(profile, data):

        if data['role']:
            profile.role = data['role']

        if data['phone']:
            profile.role = data['phone']

        # Rattachement organisation
        name = data['new_orga']
        created = False
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
            name = data['new_orga']

        elif data['is_new_orga'] is False and data['organisation']:
            organisation = data['organisation']

        profile.organisation = organisation
        profile.rattachement_active = False
        profile.save()
        if created:

            new_organisation_action = AccountActions.objects.create(
                profile=profile, action="confirm_new_organisation")
            try:
                Mail.confirm_new_organisation(request, new_organisation_action)
            except Exception as e:
                print('SendingMailError', e)
                raise e

        # Demande de rattachement Profile-Organisation
        rattachement_action = AccountActions.objects.create(
            profile=profile, action="confirm_rattachement", org_extras=organisation)

        try:
            Mail.confirm_updating_rattachement(request, rattachement_action)
        except Exception as e:
            print('SendingMailError', e)
            raise e

        # Demande de role de referent
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

        # Redaction mail de confirmation de demande de modification
        # try:
        #     Mail.confirmation_user_modification(user)
        # except Exception:
        #     pass
        profile.save()
        return profile

    user = request.user
    profile = get_object_or_404(Profile, user=user)

    if request.method == 'GET':
        return render(request, 'idgo_admin/modifyaccount.html',
                      {'uform': UserUpdateForm(instance=user),
                       'pform': ProfileUpdateForm(instance=profile,
                                                  exclude={'user': user})})

    uform = UserUpdateForm(instance=user, data=request.POST or None)
    pform = ProfileUpdateForm(
        request.POST or None, request.FILES, instance=profile, exclude={'user': user})

    if not uform.is_valid() or not pform.is_valid():
        return render(request, 'idgo_admin/modifyaccount.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'uform': uform, 'pform': pform})

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

    # print(data['new_orga'])
    # if Organisation.objects.filter(name=data['new_orga']).exists():
    #     pform.add_error('new_orga',
    #                     'Une organsiation avec ce nom existe déja. '
    #                     'Il se peut que son activation soit en attente '
    #                     'de validation par un Administrateur')
    #     return render(request, 'idgo_admin/modifyaccount.html',
    #                   {'first_name': user.first_name,
    #                    'last_name': user.last_name,
    #                    'uform': uform, 'pform': pform})

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

    return render(
        request, 'idgo_admin/modifyaccount.html',
        {'first_name': user.first_name,
         'last_name': user.last_name,
         'uform': uform,
         'pform': pform,
         'message': {
             'status': 'success',
             'text': 'Les informations de votre profil sont à jour.'}})


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def contribution_request(request):

    user = request.user
    profile = get_object_or_404(Profile, user=user)

    # Liste des organisations pour lesquelles l'user est contributeur:
    contribs = Liaisons_Contributeurs.get_contribs(profile=profile)

    if request.method == 'GET':
        return render(
            request, 'idgo_admin/publish.html',
            {'first_name': user.first_name,
             'last_name': user.last_name,
             'pform': ProfileUpdateForm(exclude={'user': user}),
             'contribs': contribs})

    pform = ProfileUpdateForm(
        instance=profile, data=request.POST or None, exclude={'user': user})

    if not pform.is_valid():
        return render(request, 'idgo_admin/publish.html', {'pform': pform})

    organisation = pform.cleaned_data['contributions']
    Liaisons_Contributeurs.objects.create(
        profile=profile, organisation=organisation)

    contribution_action = AccountActions.objects.create(
        profile=profile, action='confirm_contribution', org_extras=organisation)

    try:
        Mail.confirm_contribution(request, contribution_action)
    except Exception:
        render_an_critical_error(request)

    return render(
        request, 'idgo_admin/publish.html',
        {'first_name': user.first_name,
         'last_name': user.last_name,
         'pform': ProfileUpdateForm(exclude={'user': user}),
         'pub_liste': contribs,
         'message': {
             'status': 'success',
             'text': (
                 "Votre demande de contribution à l'organisation "
                 '<strong>{0}</strong> est en cours de traitement. Celle-ci '
                 "ne sera effective qu'après validation par un administrateur."
                 ).format(organisation.name)}})


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def referent_request(request):

    user = request.user
    profile = get_object_or_404(Profile, user=user)

    # Liste des organisations our lesquelles l'user est contributeur:
    subordonates = Liaisons_Referents.get_subordonates(profile=profile)

    if request.method == 'GET':
        return render(
            request, 'idgo_admin/publish.html',
            {'first_name': user.first_name,
             'last_name': user.last_name,
             'pform': ProfileUpdateForm(exclude={'user': user}),
             'pub_liste': subordonates})

    pform = ProfileUpdateForm(
        instance=profile, data=request.POST or None, exclude={'user': user})

    if not pform.is_valid():
        return render(request, 'idgo_admin/publish.html', {'pform': pform})

    organisation = pform.cleaned_data['referents']
    Liaisons_Referents.objects.create(
        profile=profile, organisation=organisation)
    request_action = AccountActions.objects.create(
        profile=profile, action='confirm_referent', org_extras=organisation)
    try:
        Mail.confirm_referent(request, request_action)
    except Exception:
        render_an_critical_error(request)

    return render(
        request, 'idgo_admin/publish.html',
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


# @csrf_exempt
# def publish_request_confirme(request, key):
#
#     pub_req = get_object_or_404(PublishRequest, pub_req_key=key)
#     profile = get_object_or_404(Profile, user=pub_req.user)
#     user = profile.user
#     organization = pub_req.organisation
#
#     if pub_req.date_acceptation:
#         message = ('La confirmation de la demande de '
#                    'contribution a déjà été faite.')
#         return render(request, 'idgo_admin/message.html',
#                       context={'message': message}, status=200)
#
#     if pub_req.organisation:
#         profile.publish_for.add(pub_req.organisation)
#         # ldap.add_user_to_organization(
#         #     user.username, organization.ckan_slug)
#         ckan.add_user_to_organization(
#             user.username, organization.ckan_slug, role='editor')
#         profile.save()
#
#     try:
#         Mail.publish_confirmation_to_user(publish_request)
#         pub_req.date_acceptation = timezone.now()
#         pub_req.save()
#     except Exception:
#         pass
#
#     message = ('La confirmation de la demande de contribution '
#                'a bien été prise en compte.')
#     return render(request, 'idgo_admin/message.html',
#                   context={'message': message}, status=200)


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

            # try:
            #     action = AccountActions.objects.get(
            #         action='confirm_new_organisation',
            #         profile=profile, closed__isnull=True)
            # except Exception:
            #     new_org_inactive = None
            # else:
            #     new_org_inactive = \
            #         action.org_extras.name if action.org_extras else None

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
                request, 'idgo_admin/contributions.html',
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
            'action': reverse('idgo_admin:contributions'),
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
                  context={'message': 'Votre compte a été supprimé.'}, status=200)
