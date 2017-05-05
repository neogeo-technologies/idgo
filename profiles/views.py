import os
import passlib.hash
import hashlib
import random
import smtplib
from datetime import datetime

from django.shortcuts import render
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.utils import timezone
from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth import authenticate


from .ckan_module import ckan_add_user, ckan_del_user
from .ldap_module import ldap_add_user, ldap_del_user


from .forms.user import UserForm, UserProfileForm, UserDeleteForm
from .models import Profile
from .utils import *



@csrf_exempt
def add_user(request):

    uform = UserForm(data=request.POST or None)
    pform = UserProfileForm(data=request.POST or None)

    if uform.is_valid() and pform.is_valid():

        password = uform.cleaned_data['password1']
        email_user = uform.cleaned_data['email']
        organisation = pform.cleaned_data['organisation']

        user = uform.save()
        user.password = make_password(password)
        user.username = email_user

        errors = {}
        if ldap_add_user(user, passlib.hash.ldap_sha1.encrypt(password)) is False:
            errors["LDAP"] = "Error during LDAP account creation"

        if ckan_add_user(user, password) is False:
            errors["CKAN"] = "Error during CKAN account creation"

        if errors:
            user.delete()
            return JsonResponse(data=errors,
                                status=404)
        else:
            activation_key, error = sendmail(email_user)
            if error:
                return error

            user.save()

            profile = pform.save(commit=False)
            profile.user = user
            profile.activation_key = activation_key
            profile.save()

        return JsonResponse(data={"Success": "All users created"},
                            status=200)

    else:
        return render(request, 'profiles/add.html',
                      {'context':"CREATION D'UN COMPTE UTILISATEUR",
                       'uform': uform,
                       'pform': pform})


@csrf_exempt
def update_user(request, id):

    user = get_object_or_404(User, pk=id)
    profile = get_object_or_404(Profile, user=user)

    if request.method == "GET":

        return render(request, "profiles/add.html",
                      {'context':"MODIFICATION D'UN COMPTE UTILISATEUR",
                       'uform': UserForm(instance=user, initial={'password': None}),
                       'pform': UserProfileForm(instance=profile)})

    if request.method == "POST":

        uform = UserForm(data=request.POST, instance=user)
        pform = UserProfileForm(data=request.POST, instance=profile)

        if uform.is_valid() and pform.is_valid():

            password = uform.cleaned_data['password']

            user = uform.save()

            user.password = make_password(password)
            errors = {}
            if ldap_add_user(user, passlib.hash.ldap_sha1.encrypt(password)) is False:
                errors["LDAP"] = "Error during LDAP account creation"

            if ckan_add_user(user, password) is False:
                errors["CKAN"] = "Error during CKAN account creation"

            if errors:
                # user.delete()
                return JsonResponse(data=errors,
                                    status=404)

            else:
                profile = pform.save(commit=False)
                profile.user = user
                profile.save()

            return JsonResponse(data={"Success": "All users updated"},
                                status=200)
    else:

        return render(request,
                      "profiles/user.html",
                      {'context': "MODIFICATION D'UN COMPTE UTILISATEUR",
                       'uform': UserForm(),
                       'pform': UserProfileForm()})

@csrf_exempt
def delete_user_id(request, id):

    user = get_object_or_404(User, pk=id)
    profile = get_object_or_404(Profile, user=user)

    if request.method == "GET":
        return render(request, "profiles/del.html",
                      {'context': "SUPPRESSION D'UN COMPTE UTILISATEUR",
                       'uform': UserDeleteForm(instance=user, initial={'password': None}),
                       'pform': None})

    if request.method == "POST":
        uform = UserDeleteForm(data=request.POST, instance=user)
        if uform.is_valid():

            errors = {}
            # ldap_del_user(uid)
            # ckan_del_user()

            if errors:
                return JsonResponse(data=errors,
                                    status=404)

            profile.delete()
            user.delete()
            return render(request, "profiles/success.html",
                          {'context': "SUPPRESSION REUSSI"},
                          status=200)

@csrf_exempt
def delete_user(request):
    if request.method == "GET":
        return render(request, "profiles/del.html",
                      {'context': "SUPPRESSION D'UN COMPTE UTILISATEUR",
                       'uform': UserDeleteForm(),
                       'pform': None})

    if request.method == "POST":
        uform = UserDeleteForm(data=request.POST)
        print(uform.errors.as_data())
        if uform.is_valid():
            username = uform.cleaned_data['username']
            user = get_object_or_404(User, username=username)
            profile = get_object_or_404(Profile, user=user)
            errors = {}

            # ldap_del_user(uid)
            # ckan_del_user()

            if errors:
                return JsonResponse(data=errors,
                                    status=404)

            profile.delete()
            user.delete()
            return render(request, "profiles/success.html",
                          {'context': "SUPPRESSION REUSSI"},
                          status=200)
        else:
            return render(request, 'profiles/del.html',
                          {'context': "SUPRESSION D'UN COMPTE UTILISATEUR",
                           'uform': uform,
                           'pform': None})


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
