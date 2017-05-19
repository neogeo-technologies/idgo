import hashlib
import random
import smtplib

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from .ckan_module import CkanHandler as ckan
from .ldap_module import LdapHandler as ldap
from .forms.user import UserForm, UserProfileForm, UserDeleteForm, \
                        UserUpdateForm, ProfileUpdateForm, UserLoginForm
from .models import Organisation, Profile, Registration
from .utils import *


@csrf_exempt
def sign_in(request):

    if request.method == 'GET':
        return render(
                    request, 'profiles/signin.html', {'uform': UserLoginForm()})

    uform = UserLoginForm(data=request.POST)
    if not uform.is_valid():
        uform.add_error('username', 'Vérifiez le nom de connexion !')
        uform.add_error('password', 'Vérifiez le mot de passe !')
        return render(request, 'profiles/signin.html', {'uform': uform})

    user = User.objects.get(username=uform.cleaned_data['username'])
    if not user.is_active:
        uform.add_error('username', 'Votre compte est inactif !')
        return render(request, 'profiles/signin.html', {'uform': uform})

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')

    return redirect('main')


@csrf_exempt
def sign_out(request):
    logout(request)
    return redirect('signIn')


@csrf_exempt
def sign_up(request):

    if request.method == 'GET':
        return render(request, 'profiles/signup.html',
                      {'uform': UserForm(), 'pform': UserProfileForm()})

    # class EMailIntegrityError(IntegrityError):
    #     pass

    def save_user(data):

        # if User.objects.filter(email=data['email']).exists():
        #     raise EMailIntegrityError

        user = User.objects.create_user(
                        username=data['username'], password=data['password'],
                        email=data['email'], first_name=data['first_name'],
                        last_name=data['last_name'],
                        is_staff=False, is_superuser=False, is_active=False)
        user.save()

        Registration.objects.create(
                        user=user,
                        activation_key=data['activation_key'],
                        profile_fields={'role': data['role'],
                                        'phone': data['phone'],
                                        'organisation': data['organisation']})
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
            'phone': pform.cleaned_data['phone']}

    if ckan.is_user_exists(data['username']) \
                or ldap.is_user_exists(data['username']):
        uform.add_error('username', 'Cet identifiant de connexion est réservé.')
        return render_on_error()

    try:
        user = save_user(data)
    except IntegrityError:
        uform.add_error('username', 'Cet identifiant de connexion est réservé.')
        return render_on_error()

    # except EMailIntegrityError:
    #     uform.add_error('email', 'Cet e-mail est réservé.')
    #     return render(request, 'profiles/add.html', {'uform': uform,
    #                                                  'pform': pform})

    error = []
    try:
        ldap.add_user(user, data['password'])
    except Exception as e:
        error.append(str(e))
        user.delete()

    try:
        ckan.add_user(user, data['password'])
    except Exception as e:
        error.append(str(e))
        user.delete()

    try:
        send_validation_mail(request, data['email'], data['activation_key'])
    except smtplib.SMTPException as e:
        error.append(str(e))
        user.delete()
    except Exception as e:
        error.append(str(e))

    if error:
        message = "Une erreur critique s'est produite lors de la création de " \
                  "votre compte. Merci de contacter l'administrateur du site."

        return render(request, 'profiles/failure.html',
                      {'message': message}, status=400)

    message = 'Votre compte a bien été créé. Vous recevrez un e-mail ' \
              "de confirmation d'ici quelques minutes. Pour activer " \
              'votre compte, cliquer sur le lien qui vous sera indiqué ' \
              "dans les 48h après réception de l'e-mail."

    return render(request, 'profiles/success.html',
                  {'message': message}, status=200)


@csrf_exempt
def activation(request, key):

    reg = get_object_or_404(Registration, activation_key=key)
    organisation = get_object_or_404(
                        Organisation, pk=reg.profile_fields['organisation'])

    user = reg.user
    user.is_active = True
    user.save()

    Profile.objects.create(user=user,
                           organisation=organisation,
                           phone=reg.profile_fields['phone'],
                           role=reg.profile_fields['role'])

    # Vider la table Registration pour le meme user
    Registration.objects.filter(user=user).delete()

    # Activer l'utilisateur dans CKAN:
    ckan.activate_user(user)

    # Envoyer mail de confirmation
    send_confirmation_mail(user.email)
    message = 'Votre compte est désormais activé.'

    return render(request, 'profiles/success.html',
                  {'message': message}, status=200)


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
    try:
        ldap.update_user(user, password=uform.cleaned_data['password1'])
    except:
        message = "Une erreur critique s'est produite lors de la " \
                  'mise à jour de votre compte. Merci de contacter ' \
                  "l'administrateur du site."
        return render(request, 'profiles/failure.html',
                      {'message': message}, status=400)

    try:
        ckan.update_user(user)
    except:
        # TODO: Si erreur, retablir LDAP
        message = "Une erreur critique s'est produite lors de la " \
                  "mise à jour de votre compte. Merci de contacter " \
                  "l'administrateur du site."
        return render(request, 'profiles/failure.html',
                      {'message': message}, status=400)


    try:
        uform.save_f(request)
    except ValidationError:
        return render(request, 'profiles/modifyaccount.html',
                      {'uform': uform, 'pform': pform})

    # pform.save_f()

    return render(request, 'profiles/main.html', {'uform': uform})


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
