import os
import passlib.hash
import hashlib
import random
import smtplib
from datetime import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt

from django.contrib.auth import authenticate, logout, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, get_object_or_404

from .ckan_module import CkanHandler as ckan
from .ldap_module import LdapHandler as ldap
from .forms.user import UserForm, UserProfileForm, UserDeleteForm, UserUpdateForm, ProfileUpdateForm, UserLoginForm
from .models import Profile, Organisation, Registration, EmailAlreadyExist
from .utils import *



@csrf_exempt
def login_view(request):

    uform = UserLoginForm(data=request.POST or None)
    if not uform.is_valid():
        return render(request, 'profiles/login.html', {'uform': uform})

    username = uform.cleaned_data['username']
    password = uform.cleaned_data['password']
    if not authenticate(username=username, password=password):
        uform.add_error('username', 'Vérifiez le nom de connexion !')
        uform.add_error('password', 'Vérifiez le mot de passe !')
        return render(request, 'profiles/login.html', {'uform': uform})

    user = User.objects.get(username=username)

    if not user.is_active:
        uform.add_error('username', 'Votre compte est inactif !')
        return render(request, 'profiles/login.html', {'uform': uform})

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return render(request, 'profiles/main.html', {'uform': uform})

def logout_view(request):

    logout(request)
    return redirect('login')


@csrf_exempt
def add_user(request):

    def save_user(data):
        user = User.objects.create_user(
                        username=data['username'], password=data['password'],
                        email=data['email'], first_name=data['first_name'],
                        last_name=data['last_name'],
                        is_staff=False, is_superuser=False, is_active=False)

        # Params send for post_save signal on User instance: create_registration()
        user._activation_key = data['activation_key']
        user._profile_fields = {'role': data['role'],
                                'phone': data['phone'],
                                'organisation': data['organisation']}

        user.save()


        return user

    def create_activation_key(email_user):
        pwd = str(random.random()).encode('utf-8')
        salt = hashlib.sha1(pwd).hexdigest()[:5].encode('utf-8')
        return hashlib.sha1(salt + bytes(email_user, 'utf-8')).hexdigest()

    uform = UserForm(data=request.POST or None)
    pform = UserProfileForm(data=request.POST or None)

    if not uform.is_valid() or not pform.is_valid():
        return render(request, 'profiles/add.html', {'uform': uform,
                                                     'pform': pform})

    if uform.cleaned_data['password1'] != uform.cleaned_data['password2']:
        uform.add_error('password1', 'Vérifiez les champs mot de passe')
        return render(request, 'profiles/add.html', {'uform': uform,
                                                     'pform': pform})

    data = {'activation_key': create_activation_key(uform.cleaned_data['email']),
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
        return render(request, 'profiles/add.html', {'uform': uform,
                                                     'pform': pform})

    try:
        user = save_user(data)
    except EmailAlreadyExist:
        uform.add_error('email', 'Adresse mail réservée')
    except IntegrityError:
        uform.add_error('username', 'Un utilisateur portant le même '
                                    'identifiant de connexion existe déjà.')
        return render(request, 'profiles/add.html', {'uform': uform,
                                                     'pform': pform})

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
        print(error)
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


@login_required(login_url='/profiles/login/')
@csrf_exempt
def update_user(request):

    user = request.user

    profile = get_object_or_404(Profile, user=user)

    uform = UserUpdateForm(instance=user, data=request.POST or None)
    pform = ProfileUpdateForm(instance=profile, data=request.POST or None)

    if not uform.is_valid() or not pform.is_valid():
        return render(request, 'profiles/account.html',
                      {'uform': uform, 'pform': pform})

    #Integrer ldap ckan

    uform.save_f(request)
    pform.save()

    return render(request, 'profiles/main.html', {'uform': uform})


@csrf_exempt
def delete_user(request):
    user = request.user

    uform = UserDeleteForm(data=request.POST or None)

    if not uform.is_valid():
        return render(request, 'profiles/del.html', {'uform': uform})

    user.delete()
    logout(request)
    return render(request, 'profiles/success.html',
                  {'message': 'Votre compte a été supprimé.'}, status=200)



# def register(request):
#     if request.user.is_authenticated():
#         return redirect('/index')
#     registration_form = RegistrationForm()
#     if request.method == 'POST':
#         form = RegistrationForm(data=request.POST)
#         if form.is_valid():
#             data={}
#             data['username']=form.cleaned_data['username']
#             data['email']=form.cleaned_data['email']
#             data['password1']=form.cleaned_data['password1']
#
#             #We generate a random activation key
#             salt = hashlib.sha1(str(random.random()).encode('utf-8')).hexdigest()[:5].encode('utf-8')
#             usernamesalt = data['username'].encode('utf-8')
#
#             data['activation_key'] = hashlib.sha1(salt+usernamesalt).hexdigest()
#
#             data['email_path']="/ActivationEmail.txt"
#             data['email_subject']="Activation de votre compte yourdomain"
#
#             form.sendEmail(data)
#             form.save(data) #Save the user and his profile
#
#             request.session['registered']=True #For display purposes
#             return redirect('/index')
#         else:
#             registration_form = form #Display form with error messages (incorrect fields, etc)
#     return render(request, 'register.html', locals())
#
#
# #View called from activation email. Activate user if link didn't expire (48h default), or offer to
# #send a second link if the first expired.
# def activation(request, key):
#     activation_expired = False
#     already_active = False
#     profile = get_object_or_404(Profile, activation_key=key)
#     if not profile.user.is_active:
#         if timezone.now() > profile.key_expires:
#             activation_expired = True    #Display: offer the user to send a new activation link
#             id_user = profile.user.id
#         else:    #Activation successful
#             profile.user.is_active = True
#             profile.user.save()
#
#     #If user is already active, simply display error message
#     else:
#         already_active = True #Display : error message
#     return render(request, 'activation.html', locals())
#
#
# def new_activation_link(request, user_id):
#     form = RegistrationForm()
#     datas={}
#     user = User.objects.get(id=user_id)
#     if user is not None and not user.is_active:
#         datas['username']=user.username
#         datas['email']=user.email
#         datas['email_path']="/ResendEmail.txt"
#         datas['email_subject']="Nouveau lien d'activation yourdomain"
#
#         salt = hashlib.sha1(str(random.random())).hexdigest()[:5]
#         usernamesalt = datas['username']
#         if isinstance(usernamesalt, unicode):
#             usernamesalt = usernamesalt.encode('utf8')
#         datas['activation_key']= hashlib.sha1(salt+usernamesalt).hexdigest()
#
#         profile = Profile.objects.get(user=user)
#         profile.activation_key = datas['activation_key']
#         profile.key_expires = datetime.datetime.strftime(datetime.datetime.now() + datetime.timedelta(days=2), "%Y-%m-%d %H:%M:%S")
#         profile.save()
#
#         form.sendEmail(datas)
#         request.session['new_link']=True #Display: new link sent
#
#     return redirect(home)
