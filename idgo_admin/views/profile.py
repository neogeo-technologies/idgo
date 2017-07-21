from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.forms.profile import ProfileUpdateForm
from idgo_admin.forms.profile import UserDeleteForm
from idgo_admin.forms.profile import UserForgetPassword
from idgo_admin.forms.profile import UserForm
from idgo_admin.forms.profile import UserLoginForm
from idgo_admin.forms.profile import UserProfileForm
from idgo_admin.forms.profile import UserResetPassword
from idgo_admin.forms.profile import UserUpdateForm
# from idgo_admin.models import AccountActions  # TODO(cbenhabib)
from idgo_admin.models import Dataset
from idgo_admin.models import Financeur
from idgo_admin.models import License
from idgo_admin.models import Mail
from idgo_admin.models import Organisation
from idgo_admin.models import OrganisationType
from idgo_admin.models import Profile
from idgo_admin.models import PublishRequest
from idgo_admin.models import Registration
from idgo_admin.models import Status
import json


def render_an_critical_error(request, error=None):
    # TODO(@m431m)
    message = ("Une erreur critique s'est produite lors de la création de "
               "votre compte. Merci de contacter l'administrateur du site. ")

    return render(request, 'idgo_admin/response.htm',
                  {'message': message}, status=400)


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def home(request):

    user = request.user
    datasets = [(o.pk,
                 o.name,
                 o.description,
                 o.date_creation.isoformat() if o.date_creation else None,
                 o.date_modification.isoformat() if o.date_modification else None,
                 Organisation.objects.get(id=o.organisation_id).name,
                 o.published) for o in Dataset.objects.filter(editor=user)]

    ppf = Profile.publish_for.through
    set = ppf.objects.filter(profile__user=user)
    my_pub_l = [e.organisation_id for e in set]
    is_contributor = len(Organisation.objects.filter(pk__in=my_pub_l)) > 0

    return render(request, 'idgo_admin/home.html',
                  {'first_name': user.first_name,
                   'last_name': user.last_name,
                   'datasets': json.dumps(datasets),
                   'is_contributor': json.dumps(is_contributor)}, status=200)


@csrf_exempt
def sign_in(request):

    if request.method == 'GET':
        logout(request)
        return render(request, 'idgo_admin/signin.html',
                      {'uform': UserLoginForm()})

    uform = UserLoginForm(data=request.POST)
    if not uform.is_valid():
        uform.add_error('username', 'Vérifiez votre nom de connexion !')
        uform.add_error('password', 'Vérifiez votre mot de passe !')
        return render(request, 'idgo_admin/signin.html', {'uform': uform})

    user = uform.get_user()
    request.session.set_expiry(3600)  # time-out de la session
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    nxt_pth = request.GET.get('next', None)
    if nxt_pth:
        return HttpResponseRedirect(nxt_pth)
    return redirect('idgo_admin:home')


@csrf_exempt
def sign_out(request):
    logout(request)
    return redirect('idgo_admin:signIn')


@csrf_exempt
def sign_up(request):

    if request.method == 'GET':
        return render(request, 'idgo_admin/signup.html',
                      {'uform': UserForm(), 'pform': UserProfileForm()})

    def save_user(data):

        user = User.objects.create_user(
            username=data['username'], password=data['password'],
            email=data['email'], first_name=data['first_name'],
            last_name=data['last_name'],
            is_staff=False, is_superuser=False, is_active=False)

        # TODO(cbenhabib): Registration -> AccountActions
        reg = Registration.objects.create(
            user=user, profile_fields={'role': data['role'],
                                       'phone': data['phone'],
                                       'organisation': data['organisation'],
                                       'website': data['website'],
                                       'is_new_orga': data['is_new_orga'],
                                       'parent': data['parent'].id,
                                       'organisation_type': data['organisation_type'].id,
                                       'code_insee': data['code_insee'],
                                       'description': data['description'],
                                       'adresse': data['adresse'],
                                       'code_postal': data['code_postal'],
                                       'ville': data['ville'],
                                       'org_phone': data['org_phone'],
                                       'financeur': data['financeur'].id,
                                       'status': data['status'].id,
                                       'license': data['license'].id})
        # TODO(cbenhabib): determiner si on crée une orga non active pour deporter profile_fields
        # signup_action = AccountActions.object.create(user=user, action="confirm_mail")
        # contrib_action = AccountActions.objects.create(user=user, action="confirm_mail_contrib")


        return user, reg

    def delete_user(username):
        User.objects.get(username=username).delete()

    def render_on_error():
        return render(request, 'idgo_admin/signup.html',
                      {'uform': uform, 'pform': pform})

    uform = UserForm(data=request.POST)
    pform = UserProfileForm(data=request.POST)

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

    data = {'username': uform.cleaned_data['username'],
            'email': uform.cleaned_data['email'],
            'password': uform.cleaned_data['password1'],
            'first_name': uform.cleaned_data['first_name'],
            'last_name': uform.cleaned_data['last_name'],
            'organisation': pform.cleaned_data['organisation'],
            'role': pform.cleaned_data['role'],
            'phone': pform.cleaned_data['phone'],
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
            'is_new_orga': pform.cleaned_data['is_new_orga']}

    # if ckan.is_user_exists(data['username']) \
    #         or ldap.is_user_exists(data['username']):
    if ckan.is_user_exists(data['username']):
        uform.add_error('username',
                        'Cet identifiant de connexion est réservé.')
        return render_on_error()

    try:
        user, reg = save_user(data)
    except IntegrityError:
        uform.add_error('username',
                        'Cet identifiant de connexion est réservé.')
        return render_on_error()

    try:
        # ldap.add_user(user, data['password'])
        ckan.add_user(user, data['password'])
        Mail.validation_user_mail(request, reg)
    except Exception as e:
        # delete_user(user.username)  # TODO
        print('Exception', e)
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

    user = get_object_or_404(User, email=form.cleaned_data["email"])

    # TODO(cbenhabib): Registration -> AccountActions
    # Get or create: cas ou la table Registration a été vidé (CRON à 48h)
    reg, created = Registration.objects.get_or_create(user=user)
    # reg, created = AccountActions.objects.get_or_create(user=user, action='reset_password')
    # if created is False:
    #     message = ('Un e-mail de réinitialisation à déjà été envoyé '
    #                '"'Veuillez vérifier votre messagerie')
    #     status = 200
    #     return render(request, 'idgo_admin/message.html',
    #                   {'message': message}, status=status)
    try:
        Mail.send_reset_password_link_to_user(request, reg)
    except Exception as e:
        message = ("Une erreur s'est produite lors de l'envoi du mail "
                   "de réinitialisation: {error}".format(error=e))

        status = 400
    else:
        message = ('Vous recevrez un e-mail '
                   "de réinitialisation de mot de passe d'ici quelques minutes. "
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

    # TODO(cbenhabib): Registration -> AccountActions
    reg = get_object_or_404(Registration, reset_password_key=key)
    user = get_object_or_404(User, username=reg.user.username)
    # reset_action = get_object_or_404(AccountActions, key=key, action="reset_password")
    # user = reset_action.user

    # MAJ MDP: TODO() a voir en fonction du SSO
    error = False
    try:
        with transaction.atomic():
            raise Exception('TODO!!!')  # TODO(@cbenhabib) <-------------------
        #     user = form.save(request, user)
        #     ckan.update_user(user)
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
def confirmation_email(request, key):

    # confirmation de l'email par l'utilisateur
    
    # TODO(cbenhabib): Registration -> AccountActions
    reg = get_object_or_404(Registration, activation_key=key)
    # activation_action = get_object_or_404(AccountActions, key=key, action='confirm_mail')
    # if activation_action.closed:
    #     message = "Vous avez déjà validé votre adresse e-mail."
    #     return render(request, 'idgo_admin/message.html',
    #                   {'message': message}, status=200)

    if reg.date_validation_user:
        message = "Vous avez déjà validé votre adresse e-mail."
        return render(request, 'idgo_admin/message.html',
                      {'message': message}, status=200)

    user = reg.user
    user.is_active = True
    try:
        # ldap.activate_user(user.username)
        ckan.activate_user(user.username)
    except Exception:
        return render_an_critical_error(request)

    user.save()

    Profile.objects.get_or_create(
        user=user, defaults={'phone': reg.profile_fields['phone'],
                             'role': reg.profile_fields['role']})

    if reg.profile_fields['organisation'] not in ['', None]:
        try:
            Mail.affiliate_request_to_administrators(request, reg)
        except Exception:
            return render_an_critical_error(request)

    try:
        Mail.confirmation_user_mail(user)
        # send_confirmation_mail(
        #     user.first_name, user.last_name, user.username, user.email)
    except Exception:
        pass  # Ce n'est pas très grave si l'e-mail ne part pas...

    reg.date_validation_user = timezone.now()
    reg.save()
    message = ("Merci d'avoir confirmer votre adresse e-mail. "
               'Si vous avez fait une demande de rattachement à une '
               "organisation, celle-ci ne sera effective qu'après "
               'validation par un administrateur.')

    return render(request, 'idgo_admin/message.html',
                  {'message': message}, status=200)


@csrf_exempt
def activation_admin(request, key):

    reg = get_object_or_404(Registration, affiliate_orga_key=key)
    username = reg.user.username
    profile = get_object_or_404(Profile, user=reg.user)

    if reg.date_affiliate_admin:
        message = ("Le compte <strong>{0}</strong> est déjà activé.").format(
            reg.user.username)
        return render(request, 'idgo_admin/message.html',
                      {'message': message}, status=200)

    org_name = reg.profile_fields['organisation']
    if org_name:

        d = {'organisation_type': OrganisationType,
             'parent': Organisation,
             'financeur': Financeur,
             'status': Status,
             'license': License}
        res = {}
        for key, model in d.items():
            try:
                res[key] = model.objects.get(
                        id=reg.profile_fields[key])
            except:
                res[key] = None

        org, created = Organisation.objects.get_or_create(
            name=org_name, defaults={
                'website': reg.profile_fields['website'],
                'parent': res['parent'],
                'organisation_type': res['organisation_type'],
                'code_insee': reg.profile_fields['code_insee'],
                'description': reg.profile_fields['description'],
                'adresse': reg.profile_fields['adresse'],
                'code_postal': reg.profile_fields['code_postal'],
                'ville': reg.profile_fields['ville'],
                'org_phone': reg.profile_fields['org_phone'],
                'financeur': res['financeur'],
                'status': res['status'],
                'license': res['license'],
                'email': 'xxxxxxx@xxxxxx.xxxx'})

        profile.organisation = org
        profile.save()
    else:  # Est-ce tjs nécessaire ?
        profile.organisation = None
        profile.save()
    try:
        Mail.affiliate_confirmation_to_user(profile)
    except Exception:
        pass  # Ce n'est pas très grave si l'e-mail ne part pas...

    reg.date_affiliate_admin = timezone.now()
    reg.save()
    message = ('Le compte <strong>{0}</strong> est désormais activé et son '
               'rattachement à {1} est effectif'
               ).format(username, profile.organisation.name)

    return render(request, 'idgo_admin/message.html',
                  context={'message': message}, status=200)


@transaction.atomic
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def modify_account(request):

    user = request.user
    profile = get_object_or_404(Profile, user=user)

    uform = UserUpdateForm(instance=user, data=request.POST or None)
    pform = ProfileUpdateForm(
        instance=profile, data=request.POST or None, exclude={'user': user})

    if not uform.is_valid() or not pform.is_valid():
        return render(request, 'idgo_admin/modifyaccount.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'uform': uform, 'pform': pform})

    error = False
    try:
        with transaction.atomic():
            uform.save_f(request)
            pform.save_f()
            ckan.update_user(user, profile=profile)
            # ldap.update_user(user, profile=profile,
            #                  password=uform.cleaned_data['password1'])
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
            # ldap.update_user(user)
        except Exception:
            pass
        render_an_critical_error(request)

    return render(request, 'idgo_admin/modifyaccount.html',
                  {'first_name': user.first_name,
                   'last_name': user.last_name,
                   'uform': uform,
                   'pform': pform,
                   'message': {
                       'status': 'success',
                       'text': 'Les informations de votre profil sont à jour.'}})


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def publish_request(request):

    user = request.user
    profile = get_object_or_404(Profile, user=user)
    pub_liste = profile.publish_for
    if request.method == 'GET':
        return render(
            request, 'idgo_admin/publish.html',
            {'first_name': user.first_name,
             'last_name': user.last_name,
             'pform': ProfileUpdateForm(exclude={'user': user}),
             'pub_liste': pub_liste})

    pform = ProfileUpdateForm(
        instance=profile, data=request.POST or None, exclude={'user': user})

    if not pform.is_valid():
        return render(request, 'idgo_admin/publish.html', {'pform': pform})

    pub_req = PublishRequest.objects.create(
        user=user, organisation=pform.cleaned_data['publish_for'])
    try:
        Mail.publish_request_to_administrators(request, pub_req)
    except Exception:
        render_an_critical_error(request)

    return render(
        request, 'idgo_admin/publish.html',
        {'first_name': user.first_name,
         'last_name': user.last_name,
         'pform': ProfileUpdateForm(exclude={'user': user}),
         'pub_liste': pub_liste,
         'message': {
             'status': 'success',
             'text': (
                 "Votre demande de contribution à l'organisation "
                 '<strong>{0}</strong> est en cours de traitement. Celle-ci '
                 "ne sera effective qu'après validation par un administrateur."
                 ).format(pub_req.organisation.name)}})


@csrf_exempt
def publish_request_confirme(request, key):

    pub_req = get_object_or_404(PublishRequest, pub_req_key=key)
    profile = get_object_or_404(Profile, user=pub_req.user)
    user = profile.user
    organization = pub_req.organisation

    if pub_req.date_acceptation:
        message = ('La confirmation de la demande de '
                   'contribution a déjà été faite.')
        return render(request, 'idgo_admin/message.html',
                      context={'message': message}, status=200)

    if pub_req.organisation:
        profile.publish_for.add(pub_req.organisation)
        # ldap.add_user_to_organization(
        #     user.username, organization.ckan_slug)
        ckan.add_user_to_organization(
            user.username, organization.ckan_slug, role='editor')
        profile.save()

    try:
        Mail.publish_confirmation_to_user(publish_request)
        pub_req.date_acceptation = timezone.now()
        pub_req.save()
    except Exception:
        pass

    message = ('La confirmation de la demande de contribution '
               'a bien été prise en compte.')
    return render(request, 'idgo_admin/message.html',
                  context={'message': message}, status=200)


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class Contributions(View):

    def get(self, request):
            user = request.user
            profile = get_object_or_404(Profile, user=user)
            organizations = [
                (o.organisation.id, o.organisation.name)
                for o in Profile.publish_for.through.objects.filter(profile_id=profile.id)]

            return render(
                request, 'idgo_admin/contributions.html',
                context={'first_name': user.first_name,
                         'last_name': user.last_name,
                         'organizations': json.dumps(organizations)})

    def delete(self, request):

        organization_id = request.POST.get('id', request.GET.get('id')) or None
        if not organization_id:
            return render_an_critical_error(request)

        organization = Organisation.objects.get(id=organization_id)
        profile = get_object_or_404(Profile, user=request.user)
        set = Profile.publish_for.through.objects.get(
            profile_id=profile.id, organisation_id=organization_id)
        set.delete()

        context = {
            'action': reverse('idgo_admin:contributions'),
            'message': ("Vous n'êtes plus contributeur pour l'organisation "
                        "<strong>{0}</strong>").format(organization.name)}

        return render(
            request, 'idgo_admin/response.htm', context=context, status=200)


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
        print(e)
        pass

    return render(request, 'idgo_admin/message.html',
                  context={'message': 'Votre compte a été supprimé.'}, status=200)
