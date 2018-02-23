# Copyright (c) 2017-2018 Datasud.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.models import AccountActions
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import Mail
from uuid import UUID


@ExceptionsHandler(ignore=[Http404])
@csrf_exempt
def confirmation_mail(request, key):

    action = get_object_or_404(
        AccountActions, key=UUID(key), action='confirm_mail')
    if action.closed:
        message = 'Vous avez déjà validé votre adresse e-mail.'
        return render(
            request, 'idgo_admin/message.html', {'message': message}, status=200)

    user = action.profile.user
    profile = action.profile
    organisation = profile.organisation

    ckan.activate_user(user.username)
    user.is_active = True
    action.profile.is_active = True

    user.save()
    action.profile.save()
    if organisation:
        # Demande de création d'une nouvelle organisation
        if not organisation.is_active:
            new_organisation_action = get_object_or_404(
                AccountActions,
                action='confirm_new_organisation',
                organisation=organisation,
                profile=profile,
                closed=None)
            Mail.confirm_new_organisation(request, new_organisation_action)

        # Demande de rattachement (Profile-Organisation)
        rattachement_action = get_object_or_404(
            AccountActions,
            action='confirm_rattachement',
            organisation=organisation,
            profile=profile,
            closed=None)
        Mail.confirm_rattachement(request, rattachement_action)

        # Demande de rôle de référent en attente de validation
        try:
            LiaisonsReferents.objects.get(
                organisation=organisation,
                profile=profile,
                validated_on=None)
        except Exception:
            pass
        else:
            referent_action = get_object_or_404(
                AccountActions,
                action='confirm_referent',
                organisation=organisation,
                profile=profile,
                closed=None)
            Mail.confirm_referent(request, referent_action)

        # Demande de rôle de contributeur en attente de validation
        try:
            LiaisonsContributeurs.objects.get(
                profile=profile,
                organisation=organisation,
                validated_on=None)
        except Exception:
            pass
        else:
            contribution_action = get_object_or_404(
                AccountActions,
                action='confirm_contribution',
                organisation=organisation,
                profile=profile,
                closed=None)
            Mail.confirm_contribution(request, contribution_action)

    Mail.confirmation_user_mail(user)

    action.closed = timezone.now()
    action.save()
    message = ("Merci d'avoir confirmé votre adresse e-mail. "
               'Toute demande de rattachement, contribution, '
               'ou rôle de référent technique pour une organisation, '
               "ne sera effective qu'après validation "
               'par un administrateur.')

    context = {
        'message': message,
        'button': {
            'href': reverse('idgo_admin:signIn'),
            'label': 'Se connecter'}}

    return render(request, 'idgo_admin/message.html', context, status=200)


@ExceptionsHandler(ignore=[Http404])
@csrf_exempt
def confirm_new_orga(request, key):

    action = get_object_or_404(
        AccountActions, key=UUID(key), action='confirm_new_organisation')

    name = action.organisation.name
    if action.closed:
        message = \
            "La création de l'organisation <strong>{0}</strong> a déjà été confirmée.".format(name)

    else:
        action.organisation.is_active = True
        action.organisation.save()
        # ckan.add_organization(action.profile.organisation)  # TODO À la création du premier dataset
        action.closed = timezone.now()
        action.save()
        message = ("L'organisation <strong>{0}</strong> a bien été créée. "
                   "Des utilisateurs peuvent désormais y être rattachés, "
                   "demander à en être contributeur ou référent technique. ").format(name)

    return render(request, 'idgo_admin/message.html',
                  {'message': message}, status=200)


@ExceptionsHandler(ignore=[Http404])
@csrf_exempt
def confirm_rattachement(request, key):

    action = get_object_or_404(
        AccountActions, key=UUID(key), action='confirm_rattachement')

    if action.closed:
        action.profile.membership = True
        action.profile.save()
        name = action.organisation.name
        user = action.profile.user
        message = (
            "Le rattachement de <strong>{first_name} {last_name}</strong> (<strong>{username}</strong>) "
            "à l'organisation <strong>{organization_name}</strong> a déjà été confirmée."
            ).format(first_name=user.first_name,
                     last_name=user.last_name,
                     username=user.username,
                     organization_name=name)
    else:
        name = action.organisation.name
        user = action.profile.user
        if not action.organisation.is_active:
            message = (
                '<span class="text-is-red">Le rattachement de '
                '<strong>{first_name} {last_name}</strong> '
                '(<strong>{username}</strong>) '
                "à l'organisation <strong>{organization_name}</strong> "
                'ne peut être effective que lorsque '
                'la création de cette organisation a été confirmé '
                'par un administrateur</span>.'
                ).format(first_name=user.first_name,
                         last_name=user.last_name,
                         username=user.username,
                         organization_name=name)

        else:
            action.profile.membership = True
            action.profile.organisation = action.organisation
            action.profile.save()
            action.closed = timezone.now()
            action.save()
            message = (
                "Le rattachement de <strong>{first_name} {last_name}</strong> (<strong>{username}</strong>) "
                "à l'organisation <strong>{organization_name}</strong> a bien été confirmée."
                ).format(first_name=user.first_name,
                         last_name=user.last_name,
                         username=user.username,
                         organization_name=name)

    return render(request, 'idgo_admin/message.html',
                  {'message': message}, status=200)


@ExceptionsHandler(ignore=[Http404])
@csrf_exempt
def confirm_referent(request, key):

    action = get_object_or_404(
        AccountActions, key=UUID(key), action='confirm_referent')

    organisation = action.organisation
    user = action.profile.user
    if action.closed:
        status = 200
        message = (
            "Le rôle de référent technique de l'organisation "
            '<strong>{organization_name}</strong> '
            "a déjà été confirmée pour <strong>{username}</strong>."
            ).format(organization_name=organisation.name,
                     username=user.username)
    else:
        try:
            ref_liaison = LiaisonsReferents.objects.get(
                profile=action.profile, organisation=organisation)
        except Exception:
            status = 400
            message = ("Erreur lors de la validation du role de réferent")
        else:
            if not organisation.is_active:
                message = (
                    '<span class="text-is-red">Le statut de référent technique '
                    "pour l'organisation <strong>{organization_name}</strong> "
                    "concernant <strong>{first_name} {last_name}</strong> "
                    '(<strong>{username}</strong>) ne peut être effectif que lorsque '
                    "la création de cette organisation a été confirmé par un administrateur</span>."
                    ).format(first_name=user.first_name,
                             last_name=user.last_name,
                             username=user.username,
                             organization_name=organisation.name)
                status = 200
            else:
                # Fix confirmation referent == confirmation LiaisonContributeur
                try:
                    contrib_me = LiaisonsContributeurs.objects.get(profile=action.profile, organisation=organisation)
                except Exception:
                    status = 400
                    message = ("Erreur lors de la confirmation du rôle de contributeur")
                else:
                    contrib_me.validated_on = timezone.now()
                    contrib_me.save()
                    ref_liaison.validated_on = timezone.now()
                    ref_liaison.save()
                    action.closed = timezone.now()
                    action.save()

                    status = 200
                    message = (
                        "Le rôle de référent technique de l'organisation "
                        '<strong>{organization_name}</strong> '
                        "a bien été confirmé pour <strong>{username}</strong>."
                        ).format(organization_name=organisation.name,
                                 username=user.username)

    return render(request, 'idgo_admin/message.html',
                  {'message': message}, status=status)


@ExceptionsHandler(ignore=[Http404])
@csrf_exempt
def confirm_contribution(request, key):

    action = get_object_or_404(
        AccountActions, key=UUID(key), action='confirm_contribution')
    organisation = action.organisation

    if action.closed:
        message = (
            "Le rôle de contributeur pour l'organisation <strong>{organization_name}</strong> "
            "a déjà été confirmée pour <strong>{username}</strong>."
            ).format(organization_name=organisation.name,
                     username=action.profile.user.username)
        status = 200

    else:
        try:
            contrib_liaison = LiaisonsContributeurs.objects.get(
                profile=action.profile, organisation=organisation)
        except Exception:
            message = ("Erreur lors de la validation du rôle de contributeur")
            status = 400

        else:
            user = action.profile.user
            if not organisation.is_active:
                message = (
                    '<span class="text-is-red">Le statut de contributeur pour '
                    " l'organisation <strong>{organization_name}</strong> "
                    'concernant <strong>{first_name} {last_name}</strong> (<strong>{username}</strong>) '
                    '<strong class="text-is-red">ne peut être effective que lorsque '
                    'la création de cette organisation a été confirmé par un administrateur</span>.'
                    ).format(first_name=user.first_name,
                             last_name=user.last_name,
                             username=user.username,
                             organization_name=organisation.name)
                status = 200
            else:
                contrib_liaison.validated_on = timezone.now()
                contrib_liaison.save()
                action.closed = timezone.now()
                action.save()

                message = (
                    "Le rôle de contributeur pour l'organisation <strong>{organization_name}</strong> "
                    "a bien été confirmé pour <strong>{username}</strong>."
                    ).format(organization_name=organisation.name,
                             username=user.username)
                status = 200
                try:
                    Mail.confirm_contrib_to_user(action)
                except Exception:
                    pass

    return render(request, 'idgo_admin/message.html',
                  {'message': message}, status=status)
