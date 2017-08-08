from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.models import AccountActions
from idgo_admin.models import Liaisons_Contributeurs
from idgo_admin.models import Liaisons_Referents
from idgo_admin.models import Mail


def render_an_critical_error(request):
    # TODO(@m431m)
    message = ("Une erreur critique s'est produite lors de la validation "
               "de cette opération. "
               "Merci de contacter l'administrateur du site. ")

    return render(request, 'idgo_admin/response.html',
                  {'message': message}, status=400)


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
        AccountActions, key=str(key), action='confirm_new_organisation')

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
        AccountActions, key=str(key), action='confirm_rattachement')

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
        AccountActions, key=str(key), action='confirm_referent')

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
        AccountActions, key=str(key), action='confirm_contribution')
    organisation = action.org_extras

    if action.closed:
        message = (
            "Le rôle de contributeur pour l'organisation {organization_name} "
            "a déjà été confirmée pour <strong>{username}</strong>."
            ).format(organization_name=organisation.name,
                     username=action.profile.user.username)
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