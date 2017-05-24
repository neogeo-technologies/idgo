import hashlib
import random
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core import serializers
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.csrf import csrf_exempt

from .ckan_module import CkanHandler as ckan
from .ldap_module import LdapHandler as ldap
from .forms.user import UserForm, UserProfileForm, UserDeleteForm, \
                        UserUpdateForm, ProfileUpdateForm, UserLoginForm
from idgo_admin.models import Dataset
from .models import Organisation, Profile, Registration
from .utils import *


def render_an_critical_error(request):
    message = "Une erreur critique s'est produite lors de la création de " \
              "votre compte. Merci de contacter l'administrateur du site."

    return render(
            request, 'profiles/failure.html', {'message': message}, status=400)


@csrf_exempt
def main(request):

    if not request.user.is_authenticated:
        return sign_in(request)

    user = request.user
    datasets = serializers.serialize("json", Dataset.objects.filter(editor=user))
    return render(request, 'profiles/main.html', {'datasets':datasets},
                  status=200)

def get_param(request, param):
    """
        Retourne la valeur d'une clé param presente dans une requete GET ou POST
    """
    value = None

    if request.method == "GET" and param in request.GET:
        value = request.GET[param]

    elif request.method == "POST":
        try:
            param_read = request.POST.get(param, request.GET.get(param))
        except KeyError as e:
            return None
        value = param_read

    return value


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

    # TODO
    # try:
    #     redirect_url = request.POST.get("next", request.GET.get("next"))
    # except KeyError as e:
    #     redirect_url =  None
    #
    # print(redirect_url)

    user = uform.get_user()
    request.session.set_expiry(600) #time-out de la session
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')

    return main(request)


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

        org_publ_pk = [entry['pk'] for entry in data['publish_for'].values('pk')]
        Registration.objects.create(
                        user=user,
                        activation_key=data['activation_key'],
                        profile_fields={'role': data['role'],
                                        'phone': data['phone'],
                                        'organisation': data['organisation'],
                                        'publish_for': org_publ_pk})
        return user

    def create_activation_key(email_user):
        pwd = str(random.random()).encode('utf-8')
        salt = hashlib.sha1(pwd).hexdigest()[:5].encode('utf-8')
        return hashlib.sha1(salt + bytes(email_user, 'utf-8')).hexdigest()

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

    data = {'activation_key': create_activation_key(
                                        uform.cleaned_data['email']),
            'username': uform.cleaned_data['username'],
            'email': uform.cleaned_data['email'],
            'password': uform.cleaned_data['password1'],
            'first_name': uform.cleaned_data['first_name'],
            'last_name': uform.cleaned_data['last_name'],
            'organisation': pform.cleaned_data['organisation'],
            'role': pform.cleaned_data['role'],
            'phone': pform.cleaned_data['phone'],
            'publish_for': pform.cleaned_data['publish_for']}

    if ckan.is_user_exists(data['username']) \
                or ldap.is_user_exists(data['username']):
        uform.add_error('username', 'Cet identifiant de connexion est réservé.')
        return render_on_error()

    try:
        user = save_user(data)
    except IntegrityError:
        uform.add_error('username', 'Cet identifiant de connexion est réservé.')
        return render_on_error()

    try:
        ldap.add_user(user, data['password'])
        ckan.add_user(user, data['password'])
        send_validation_mail(request, data['email'], data['activation_key'])
    except:
        return render_an_critical_error(request)

    message = 'Votre compte a bien été créé. Vous recevrez un e-mail ' \
              "de confirmation d'ici quelques minutes. Pour activer " \
              'votre compte, cliquer sur le lien qui vous sera indiqué ' \
              "dans les 48h après réception de l'e-mail."

    return render(request, 'profiles/success.html',
                  {'message': message}, status=200)


@csrf_exempt
def activation(request, key):

    reg = get_object_or_404(Registration, activation_key=key)
    organization = get_object_or_404(
                        Organisation, pk=reg.profile_fields['organisation'])

    user = reg.user
    user.is_active = True
    user.save()
    try:
        profile = Profile.objects.create(user=user,
                                         organisation=organization,
                                         phone=reg.profile_fields['phone'],
                                         role=reg.profile_fields['role'])

        for org in reg.profile_fields['publish_for']:
            profile.publish_for.add(Organisation.objects.get(pk=org))


    except IntegrityError:
        return render_an_critical_error(request)

    try:
        ldap.add_user_to_organization(user.username, organization.ckan_slug)
        ldap.activate_user(user.username)
        ckan.add_user_to_organization(user.username, organization.ckan_slug)
        ckan.activate_user(user.username)
        Registration.objects.filter(user=user).delete()
    except Exception as e:
        profile.delete()
        # TODO: Rétablir l'état inactif du compte !
        return render_an_critical_error(request)

    try:
        send_confirmation_mail(user.email)
    except:
        pass  # Ce n'est pas très grave si l'e-mail ne part pas...

    message = 'Votre compte est désormais activé.'
    return render(request, 'profiles/success.html',
                  {'message': message}, status=200)


@transaction.atomic
@login_required(login_url='/profiles/signin/')
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
    return render(request, 'profiles/success.html', {'message': message}, status=200)


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
