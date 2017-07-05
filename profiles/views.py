from .ckan_module import CkanHandler as ckan
from .forms.user import ProfileUpdateForm
from .forms.user import UserDeleteForm
from .forms.user import UserForm
from .forms.user import UserLoginForm
from .forms.user import UserProfileForm
from .forms.user import UserUpdateForm
from .ldap_module import LdapHandler as ldap
from .models import Organisation
from .models import Profile
from .models import PublishRequest
from .models import Registration
from .utils import send_affiliate_confirmation
from .utils import send_affiliate_request
from .utils import send_confirmation_mail
from .utils import send_publish_confirmation
from .utils import send_publish_request
from .utils import send_validation_mail
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
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from idgo_admin.models import Dataset
import json


def render_an_critical_error(request, error=None):
    # TODO(@m431m)
    message = ("Une erreur critique s'est produite lors de la création de "
               "votre compte. Merci de contacter l'administrateur du site. ")

    return render(request, 'profiles/information.html',
                  {'message': message}, status=400)


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

    ppf = Profile.publish_for.through
    set = ppf.objects.filter(profile__user=user)
    my_pub_l = [e.organisation_id for e in set]
    is_contributor = len(Organisation.objects.filter(pk__in=my_pub_l)) > 0

    return render(request, 'profiles/main.html',
                  {'first_name': user.first_name,
                   'last_name': user.last_name,
                   'datasets': json.dumps(datasets),
                   'is_contributor': json.dumps(is_contributor)}, status=200)


@csrf_exempt
def sign_in(request):

    if request.method == 'GET':
        logout(request)
        return render(request, 'profiles/signin.html',
                      {'uform': UserLoginForm()})

    uform = UserLoginForm(data=request.POST)
    if not uform.is_valid():
        uform.add_error('username', 'Vérifiez le nom de connexion !')
        uform.add_error('password', 'Vérifiez le mot de passe !')
        return render(request, 'profiles/signin.html', {'uform': uform})

    user = uform.get_user()
    request.session.set_expiry(600)  # time-out de la session
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
            user=user, profile_fields={'role': data['role'],
                                       'phone': data['phone'],
                                       'organisation': data['organisation'],
                                       'new_website': data['new_website'],
                                       'is_new_orga': data['is_new_orga']})
        return user, reg

    def delete_user(username):
        User.objects.get(username=username).delete()

    def render_on_error():
        return render(request, 'profiles/signup.html',
                      {'uform': uform, 'pform': pform})

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
                        'Cet identifiant de connexion est réservé.')
        return render_on_error()

    try:
        user, reg = save_user(data)
    except IntegrityError:
        uform.add_error('username',
                        'Cet identifiant de connexion est réservé.')
        return render_on_error()

    try:
        ldap.add_user(user, data['password'])
        ckan.add_user(user, data['password'])
        send_validation_mail(request, reg)
    except Exception as e:
        # delete_user(user.username)
        return render_an_critical_error(request, e)

    message = ('Votre compte a bien été créé. Vous recevrez un e-mail '
               "de confirmation d'ici quelques minutes. Pour activer "
               'votre compte, cliquer sur le lien qui vous sera indiqué '
               "dans les 48h après réception de l'e-mail.")

    return render(request, 'profiles/information.html',
                  {'message': message}, status=200)


@csrf_exempt
def confirmation_email(request, key):

    # confirmation de l'email par l'utilisateur

    reg = get_object_or_404(Registration, activation_key=key)

    try:
        reg.key_expires = None
    except Exception:
        pass

    user = reg.user
    user.is_active = True
    user.save()

    Profile.objects.get_or_create(
        user=user, defaults={'phone': reg.profile_fields['phone'],
                             'role': reg.profile_fields['role']})

    if reg.profile_fields['organisation'] not in ['', None]:
        try:
            send_affiliate_request(request, reg)
        except Exception:
            return render_an_critical_error(request)

    try:
        send_confirmation_mail(
            user.first_name, user.last_name, user.username, user.email)
    except Exception:
        pass  # Ce n'est pas très grave si l'e-mail ne part pas...

    message = ("Merci d'avoir confirmer votre adresse email. "
               'Si vous avez fait une demande de rattachement à une '
               "organisation, celle-ci ne sera effective qu'après "
               'validation par un administrateur.')

    return render(request, 'profiles/information.html',
                  {'message': message}, status=200)


@csrf_exempt
def activation_admin(request, key):

    # Activation du compte par l'administrateur et rattachement

    reg = get_object_or_404(Registration, affiliate_orga_key=key)
    profile = get_object_or_404(Profile, user=reg.user)

    reg_org_name = reg.profile_fields['organisation']
    if reg_org_name:
        org, created = Organisation.objects.get_or_create(
            name=reg_org_name, defaults={
                'website': reg.profile_fields['new_website'],
                'email': 'xxxxxxx@xxxxxx.xxxx',
                'code_insee': '000000000000000'})

        profile.organisation = org
        profile.save()
        username = reg.user.username
        try:
            # TODO: voir si activate_user() necessite
            # add_user_to_organization()
            if reg.profile_fields['organisation']:
                ldap.add_user_to_organization(username, org.ckan_slug)
            ldap.activate_user(reg.user.username)

            if reg.profile_fields['organisation']:
                ckan.add_user_to_organization(
                    username, org.ckan_slug, role='editor')
            ckan.activate_user(username)
            reg.delete()

        except Exception:
            # profile.delete()
            # TODO: Rétablir l'état inactif du compte !
            return render_an_critical_error(request)
    else:
        profile.organisation = None
        profile.save()
        reg.delete()

    try:
        send_affiliate_confirmation(profile)
    except Exception:
        pass  # Ce n'est pas très grave si l'e-mail ne part pas...

    message = ('Le compte de {0} est désormais activé et son rattachement à '
               '{1} est effectif').format(username, profile.organisation.name)

    return render(request, 'profiles/information.html',
                  {'message': message}, status=200)


@csrf_exempt
def affiliate_request(request, key):

    reg = get_object_or_404(Registration, affiliate_orga_key=key)

    try:
        send_affiliate_confirmation(reg)
        reg.date_acceptation = timezone.now()
    except Exception:
        pass

    message = ('La confirmation de la demande de '
               'rattachement a bien été prise en compte.')

    return render(request, 'profiles/information.html',
                  {'message': message}, status=200)


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
        return render(request, 'profiles/modifyaccount.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'uform': uform, 'pform': pform})

    error = False
    try:
        with transaction.atomic():
            uform.save_f(request)
            pform.save_f()
            ckan.update_user(user, profile=profile)
            ldap.update_user(user, profile=profile,
                             password=uform.cleaned_data['password1'])

    except ValidationError:
        return render(request, 'profiles/modifyaccount.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'uform': uform, 'pform': pform})

    except IntegrityError:
        logout(request)
        error = True

    if error:
        user = User.objects.get(username=user.username)
        try:
            ckan.update_user(user)
            ldap.update_user(user)
        except Exception:
            pass
        render_an_critical_error(request)

    message = 'Les informations de votre profile sont à jour.'
    return render(request, 'profiles/information.html',
                  {'message': message}, status=200)


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def publish_request(request):

    user = request.user
    profile = get_object_or_404(Profile, user=user)
    pub_liste = profile.publish_for
    if request.method == 'GET':
        return render(
            request, 'profiles/publish.html',
            {'first_name': user.first_name,
             'last_name': user.last_name,
             'pform': ProfileUpdateForm(exclude={'user': user}),
             'pub_liste': pub_liste})

    pform = ProfileUpdateForm(
        instance=profile, data=request.POST or None, exclude={'user': user})

    if not pform.is_valid():
        return render(request, 'profiles/publish.html', {'pform': pform})

    pub_req = PublishRequest.objects.create(
        user=user, organisation=pform.cleaned_data['publish_for'])
    try:
        send_publish_request(request, pub_req)
    except Exception:
        render_an_critical_error(request)

    message = ("Votre demande de contribution à l'organisation {0}"
               'est en cours de traitement. Celle-ci sera effective après '
               'validation par un administrateur.'
               ).format(pub_req.organisation.name)

    return render(request, 'profiles/information.html',
                  {'message': message}, status=200)


@csrf_exempt
def publish_request_confirme(request, key):

    pub_req = get_object_or_404(PublishRequest, pub_req_key=key)
    profile = get_object_or_404(Profile, user=pub_req.user)

    if pub_req.date_acceptation:
        message = 'La confirmation de la demande de contribution a déjà été faite.'
        return render(request, 'profiles/information.html',
                      {'message': message}, status=200)

    if pub_req.organisation:
        profile.publish_for.add(pub_req.organisation)
        profile.save()
    try:
        send_publish_confirmation(pub_req)
        pub_req.date_acceptation = timezone.now()
        pub_req.save()
    except Exception:
        pass

    message = 'La confirmation de la demande de contribution a bien été prise en compte.'
    return render(request, 'profiles/information.html',
                  {'message': message}, status=200)


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def contributions(request):
    user = request.user
    profile = get_object_or_404(Profile, user=user)
    if request.method == 'GET':
        return render(request, 'profiles/contributions.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'my_profile': profile})


@login_required(login_url=settings.LOGIN_URL)
@csrf_exempt
def delete_account(request):
    user = request.user
    if request.method == 'GET':
        return render(request, 'profiles/deleteaccount.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'uform': UserDeleteForm()})

    user = request.user
    uform = UserDeleteForm(data=request.POST)
    if not uform.is_valid():
        return render(request, 'profiles/deleteaccount.html',
                      {'first_name': user.first_name,
                       'last_name': user.last_name,
                       'uform': uform})

    user.delete()
    logout(request)

    return render(request, 'profiles/information.html',
                  {'message': 'Votre compte a été supprimé.'}, status=200)
