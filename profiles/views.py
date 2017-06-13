import json

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .ckan_module import CkanHandler as ckan
from .ldap_module import LdapHandler as ldap
from .forms.user import UserForm, UserProfileForm, UserDeleteForm, \
    UserUpdateForm, ProfileUpdateForm, UserLoginForm
from idgo_admin.models import Dataset
from .models import Organisation, Profile, Registration, PublishRequest
from .utils import *


def render_an_critical_error(request, e=None):
    message = "Une erreur critique s'est produite lors de la création de " \
              "votre compte. Merci de contacter l'administrateur du site. " \
              "{error}".format(error=e)

    return render(
            request, 'profiles/failure.html', {'message': message}, status=400)


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def main(request):

    user = request.user

    datasets = [(o.pk,
                 o.name,
                 o.description,
                 o.date_creation.isoformat(),
                 o.date_modification.isoformat(),
                 o.published) for o in Dataset.objects.filter(editor=user)]

    return render(request, 'profiles/main.html',
                  {'datasets': json.dumps(datasets)}, status=200)

@csrf_exempt
def sign_in(request):

    if request.method == 'GET':
        logout(request)
        return render(
                    request, 'profiles/signin.html', {'uform': UserLoginForm()})

    uform = UserLoginForm(data=request.POST)
    if not uform.is_valid():
        uform.add_error('username', 'Vérifiez le nom de connexion !')
        uform.add_error('password', 'Vérifiez le mot de passe !')
        return render(request, 'profiles/signin.html', {'uform': uform})

    user = uform.get_user()
    request.session.set_expiry(600) #time-out de la session
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    nxt_pth = request.GET.get('next', None)
    if nxt_pth:
        return HttpResponseRedirect(nxt_pth)
    return redirect('profiles:main')


@csrf_exempt
def sign_out(request):
    logout(request)
    return redirect('profiles:signIn')


@csrf_exempt
def sign_up(request):

    if request.method == 'GET':
        return render(request, 'profiles/signup.html',
                      {'uform': UserForm(), 'pform': UserProfileForm()})

    def save_user(data):

        user = User.objects.create_user(
                        username=data['username'], password=data['password'],
                        email=data['email'], first_name=data['first_name'],
                        last_name=data['last_name'],
                        is_staff=False, is_superuser=False, is_active=False)

        reg = Registration.objects.create(
                        user=user,
                        profile_fields={'role': data['role'],
                                        'phone': data['phone'],
                                        'organisation': data['organisation'],
                                        'new_website': data['new_website'],
                                        'is_new_orga': data['is_new_orga'],
                                        })

        return user, reg

    def delete_user(username):
        User.objects.get(username=username).delete()

    def render_on_error():
        return render(request, 'profiles/signup.html', {'uform': uform,
                                                        'pform': pform})

    uform = UserForm(data=request.POST)
    pform = UserProfileForm(data=request.POST)

    if not uform.is_valid() or not pform.is_valid():
        return render_on_error()

    if uform.cleaned_data['password1'] != uform.cleaned_data['password2']:
        uform.add_error('password1', 'Vérifiez les champs mot de passe')
        return render_on_error()

    data = {'username': uform.cleaned_data['username'],
            'email': uform.cleaned_data['email'],
            'password': uform.cleaned_data['password1'],
            'first_name': uform.cleaned_data['first_name'],
            'last_name': uform.cleaned_data['last_name'],
            'organisation': pform.cleaned_data['organisation'],
            'new_website': pform.cleaned_data['new_website'],
            'is_new_orga': pform.cleaned_data['is_new_orga'],
            'role': pform.cleaned_data['role'],
            'phone': pform.cleaned_data['phone']}

    if ckan.is_user_exists(data['username']) \
                or ldap.is_user_exists(data['username']):
        uform.add_error('username',
                        'Cet identifiant de connexion est réservé. ')
        return render_on_error()

    try:
        user, reg = save_user(data)
    except IntegrityError:
        uform.add_error('username',
                        'Cet identifiant de connexion est réservé. ')
        return render_on_error()

    try:
        ldap.add_user(user, data['password'])
        ckan.add_user(user, data['password'])
        send_validation_mail(request, reg)
    except Exception as e:
        delete_user(user.username)
        return render_an_critical_error(request, e)

    message = 'Votre compte a bien été créé. Vous recevrez un e-mail ' \
              "de confirmation d'ici quelques minutes. Pour activer " \
              'votre compte, cliquer sur le lien qui vous sera indiqué ' \
              "dans les 48h après réception de l'e-mail."

    return render(request, 'profiles/success.html',
                  {'message': message}, status=200)


@csrf_exempt
def confirmation_email(request, key): # confirmation de l'email par l'utilisateur

    reg = get_object_or_404(Registration, activation_key=key)

    try:
        reg.key_expires = None
    except:
        pass

    user = reg.user
    user.is_active = True
    user.save()

    Profile.objects.get_or_create(user=user,
                                  defaults={"phone":reg.profile_fields['phone'],
                                            "role":reg.profile_fields['role']})


    if reg.profile_fields['organisation'] not in ['', None] :
        try:
            send_affiliate_request(request, reg)
        except:
            return render_an_critical_error(request)

    try:
        send_confirmation_mail(user.email)
    except:
        pass  # Ce n'est pas très grave si l'e-mail ne part pas...



    message = """Merci d'avoir confirmer votre adresse email,
        si vous avez fait une demande de rattachement à une organisation, 
        celle-ci sera effective après validation par un administrateur. 
        """

    return render(request, 'profiles/success.html',
                  {'message': message}, status=200)


@csrf_exempt
def activation_admin(request, key):  # activation du compte par l'administrateur et rattachement

    reg = get_object_or_404(Registration, affiliate_orga_key=key)
    profile = get_object_or_404(Profile, user=reg.user)

    reg_org_name = reg.profile_fields['organisation']
    if reg_org_name:
        org, created = Organisation.objects.get_or_create(name=reg_org_name,
                                                 defaults={"website":reg.profile_fields['new_website'],
                                              "email":"xxxxxxx@xxxxxx.xxxx",
                                              "code_insee":"000000000000000"})


        profile.organisation = org
        profile.save()
        username = reg.user.username
        try:
            # Todo: a voir si activate_user() necessite add_user_to_organization().
            if reg.profile_fields['organisation']:
                ldap.add_user_to_organization(username, org.ckan_slug)
            ldap.activate_user(reg.user.username)

            if reg.profile_fields['organisation']:
                ckan.add_user_to_organization(username, org.ckan_slug,
                                              role='editor')  # Qui détermine le rôle ?
            ckan.activate_user(username)
            reg.delete()

        except Exception as e:
            # profile.delete()
            # TODO: Rétablir l'état inactif du compte !
            return render_an_critical_error(request)

    else:
        profile.organisation = None
        profile.save()
    try:
        send_affiliate_confirmation(profile)
        reg.delete()
    except:
        pass  # Ce n'est pas très grave si l'e-mail ne part pas...

    message = 'Le compte de {username} est désormais activé. ' \
              'et son rattachement à {orga} est effectif'.format(username=username,
                                                                 orga=profile.organisation.name)
    return render(request, 'profiles/success.html',
                  {'message': message}, status=200)


@csrf_exempt
def affiliate_request(request, key):

    reg = get_object_or_404(Registration, affiliate_orga_key=key)

    try:
        send_affiliate_confirmation(reg)
        reg.date_acceptation = timezone.now()
    except:
        pass

    message = "La confirmation de la demande de rattachement a bien été prise en compte. "
    return render(request, 'profiles/success.html',
                  {'message': message}, status=200)

@transaction.atomic
@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def modify_account(request):

    user = request.user
    profile = get_object_or_404(Profile, user=user)

    uform = UserUpdateForm(instance=user, data=request.POST or None)
    pform = ProfileUpdateForm(instance=profile, data=request.POST or None)
    if not uform.is_valid() or not pform.is_valid():
        return render(request, 'profiles/modifyaccount.html', {'uform': uform,
                                                               'pform': pform})

    error = False
    try:
        with transaction.atomic():
            uform.save_f(request)
            pform.save_f()
            ckan.update_user(user, profile=profile)
            ldap.update_user(user, profile=profile,
                             password=uform.cleaned_data['password1'])

    except ValidationError:
        return render(request, 'profiles/modifyaccount.html', {'uform': uform,
                                                               'pform': pform})
    except IntegrityError:
        logout(request)
        error = True

    if error:
        user = User.objects.get(username=user.username)
        try:
            ckan.update_user(user)
            ldap.update_user(user)
        except:
            pass
        render_an_critical_error(request)

    message = 'Les informations de votre profile sont à jour.'
    return render(request, 'profiles/success.html',
                  {'message': message}, status=200)



@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def publish_request(request):

    user = request.user
    profile = get_object_or_404(Profile, user=user)
    pub_liste = profile.publish_for
    if request.method == 'GET':
        return render(request, 'profiles/publish.html',
                      {'pform': ProfileUpdateForm(),
                       "pub_liste": pub_liste})

    pform = ProfileUpdateForm(instance=profile, data=request.POST or None)

    if not pform.is_valid():
        return render(request, 'profiles/publish.html', {'pform': pform})

    pub_req = PublishRequest.objects.create(user=user, organisation=pform.cleaned_data['publish_for'])
    try:
        send_publish_request(request, pub_req)
    except:
        render_an_critical_error(request)

    message = """Votre demande de contribution à l'organisation {new_orga} est en cours de traitement.
    Celle-ci sera effective après validation par un administrateur """.format(new_orga=pub_req.organisation.name)
    return render(request, 'profiles/success.html',
                  {'message': message}, status=200)


@csrf_exempt
def publish_request_confirme(request, key):

    pub_req = get_object_or_404(PublishRequest, pub_req_key=key)
    profile = get_object_or_404(Profile, user=pub_req.user)

    if pub_req.organisation:
        profile.publish_for.add(pub_req.organisation)
        profile.save()
    try:
        send_publish_confirmation(pub_req)
        pub_req.date_acceptation = timezone.now()
    except:
        pass

    pub_req.delete()
    message = "La confirmation de la demande de contribution a bien été prise en compte. "
    return render(request, 'profiles/success.html',
                  {'message': message}, status=200)


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def delete_account(request):

    if request.method == 'GET':
        return render(request, 'profiles/deleteaccount.html',
                      {'uform': UserDeleteForm()})

    user = request.user
    uform = UserDeleteForm(data=request.POST)
    if not uform.is_valid():
        return render(request, 'profiles/deleteaccount.html', {'uform': uform})

    user.delete()
    logout(request)

    return render(request, 'profiles/success.html',
                  {'message': 'Votre compte a été supprimé.'}, status=200)
