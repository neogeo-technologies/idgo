# Copyright (c) 2017-2019 Datasud.
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


from django.apps import apps
from django.conf import settings
from django.contrib.gis.db import models
from django.core.mail import get_connection
from django.core.mail.message import EmailMultiAlternatives
from idgo_admin import logger
from idgo_admin.utils import PartialFormatter
from urllib.parse import urljoin


class Mail(models.Model):

    template_name = models.CharField(
        verbose_name='Identifiant', primary_key=True, max_length=100)

    subject = models.CharField(
        verbose_name='Objet', max_length=255, blank=True, null=True)

    message = models.TextField(
        verbose_name='Corps du message', blank=True, null=True)

    class Meta(object):
        verbose_name = 'e-mail'
        verbose_name_plural = 'e-mails'

    def __str__(self):
        return self.template_name


def get_admins_mails(crige=False):
    Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
    kwargs = {'is_active': True, 'is_admin': True}
    if crige:
        kwargs['crige_membership'] = True
    return [
        p.user.email for p in Profile.objects.filter(**kwargs)]


def get_referents_mails(organisation):
    LiaisonsReferents = apps.get_model(
        app_label='idgo_admin', model_name='LiaisonsReferents')
    return [
        l.profile.user.email for l
        in LiaisonsReferents.objects.filter(
            organisation=organisation, validated_on__isnull=False)]


def sender(template_name, to=None, cc=None, bcc=None, attach_files=[], **kvp):
    try:
        tmpl = Mail.objects.get(template_name=template_name)
    except Mail.DoesNotExist:
        return

    if to and cc:
        for v in to:
            try:
                cc.remove(v)
            except ValueError:
                continue

    if to and bcc:
        for v in to:
            try:
                bcc.remove(v)
            except ValueError:
                continue

    subject = tmpl.subject.format(**kvp)
    body = PartialFormatter().format(tmpl.message, **kvp)
    from_email = settings.DEFAULT_FROM_EMAIL
    connection = get_connection(fail_silently=False)

    mail = EmailMultiAlternatives(
        subject=subject, body=body,
        from_email=from_email, to=to,
        cc=cc, bcc=bcc, connection=connection)

    for attach_file in attach_files:
        mail.attach_file(attach_file)

    mail.send()


# Pour informer l'utilisateur de la création de son compte par un administrateur
def send_account_creation_mail(user, url):
    return sender(
        'account_creation_by_admin',
        full_name=user.get_full_name(),
        to=[user.email],
        url=url,
        username=user.username)


# Pour confirmer une demande de création de compte
def send_account_creation_confirmation_mail(user, url):
    return sender(
        'confirm_account_creation',
        full_name=user.get_full_name(),
        to=[user.email],
        url=url,
        username=user.username)


# Pour informer de la création du compte
def send_successful_account_creation_mail(user):
    return sender(
        'account_activated',
        full_name=user.get_full_name(),
        to=[user.email],
        username=user.username)


# Pour réinitialiser le mot de passe d'un compte
def send_reset_password_link_to_user(user, url):
    return sender(
        'reset_password',
        full_name=user.get_full_name(),
        to=[user.email],
        url=url,
        username=user.username)


# Pour informer l'utilisateur de la suppression de son compte
def send_account_deletion_mail(email, full_name, username):
    return sender(
        'account_deleted',
        full_name=full_name,
        to=[email],
        username=username)


# Pour confirmer une demande de statut de membre
def send_membership_confirmation_mail(user, organisation, url):
    return sender(
        'confirm_membership_status',
        bcc=list(set(get_admins_mails() + get_referents_mails(organisation))),
        email=user.email,
        full_name=user.get_full_name(),
        organisation=organisation.name,
        url=url,
        username=user.username,
        website=organisation.website or '- adresse url manquante -')


# Pour informer l'utilisateur de son statut de membre
def send_confirmed_membership_mail(user, organisation):
    return sender(
        'membership_status_confirmed',
        full_name=user.get_full_name(),
        organisation=organisation.name,
        to=[user.email],
        username=user.username)


# Pour confirmer le statut de contributeur d'un utilisateur
def send_contributor_confirmation_mail(user, organisation, url):
    return sender(
        'confirm_contributor_status',
        bcc=list(set(get_admins_mails() + get_referents_mails(organisation))),
        email=user.email,
        full_name=user.get_full_name(),
        organisation=organisation.name,
        url=url,
        username=user.username,
        website=organisation.website or '- adresse url manquante -')


# Pour informer l'utilisateur de son statut de contributeur
def send_confirmed_contribution_mail(user, organisation):
    return sender(
        'contributor_status_confirmed',
        full_name=user.get_full_name(),
        organisation=organisation.name,
        to=[user.email],
        username=user.username)


# Pour confirmer le statut de référent d'un utilisateur
def send_referent_confirmation_mail(user, organisation, url):
    return sender(
        'confirm_referent_status',
        bcc=list(set(get_admins_mails() + get_referents_mails(organisation))),
        email=user.email,
        full_name=user.get_full_name(),
        organisation=organisation.name,
        url=url,
        username=user.username,
        website=organisation.website or '- adresse url manquante -')


# Pour informer l'utilisateur de son statut de référent
def send_confirmed_referent_mail(user, organisation):
    return sender(
        'referent_status_confirmed',
        full_name=user.get_full_name(),
        organisation=organisation.name,
        to=[user.email],
        username=user.username)


# Pour confirmer une demande de création d'organisation
def send_organisation_creation_confirmation_mail(user, organisation, url):
    return sender(
        'confirm_organisation_creation',
        bcc=get_admins_mails(),
        email=user.email,
        full_name=user.get_full_name(),
        organisation=organisation.name,
        url=url,
        username=user.username,
        website=organisation.website or '- adresse url manquante -')


# Pour informer de la création d'un jeu de données
def send_dataset_creation_mail(user, dataset):
    return sender(
        'dataset_created',
        bcc=list(set(get_admins_mails() + get_referents_mails(dataset.organisation))),
        ckan_url=dataset.ckan_url,
        dataset=dataset.name,
        id=dataset.ckan_slug,
        full_name=user.get_full_name(),
        to=[user.email],
        username=user.username)


# Pour informer de la modification d'un jeu de données
def send_dataset_update_mail(user, dataset):
    return sender(
        'dataset_updated',
        bcc=list(set(get_admins_mails() + get_referents_mails(dataset.organisation))),
        ckan_url=dataset.ckan_url,
        dataset=dataset.name,
        full_name=user.get_full_name(),
        id=dataset.ckan_slug,
        to=[user.email],
        username=user.username)


# Pour informer de la suppression d'un jeu de données
def send_dataset_delete_mail(user, dataset):
    return sender(
        'dataset_deleted',
        bcc=list(set(get_admins_mails() + get_referents_mails(dataset.organisation))),
        dataset=dataset.name,
        full_name=user.get_full_name(),
        id=dataset.ckan_slug,
        to=[user.email],
        username=user.username)


# Pour informer de la création d'une ressource
def send_resource_creation_mail(user, resource):
    return sender(
        'resource_created',
        bcc=list(set(get_admins_mails() + get_referents_mails(resource.dataset.organisation))),
        ckan_url=resource.ckan_url,
        dataset=resource.dataset.name,
        full_name=user.get_full_name(),
        id=resource.ckan_id,
        resource=resource.name,
        to=[user.email],
        username=user.username)


# Pour informer de la modification d'une ressource
def send_resource_update_mail(user, resource):
    return sender(
        'resource_updated',
        bcc=list(set(get_admins_mails() + get_referents_mails(resource.dataset.organisation))),
        ckan_url=resource.ckan_url,
        dataset=resource.dataset.name,
        full_name=user.get_full_name(),
        id=resource.ckan_id,
        resource=resource.name,
        to=[user.email],
        username=user.username)


# Pour informer de la suppression d'une ressource
def send_resource_delete_mail(user, resource):
    return sender(
        'resource_deleted',
        bcc=list(set(get_admins_mails() + get_referents_mails(resource.dataset.organisation))),
        dataset=resource.dataset.name,
        full_name=user.get_full_name(),
        id=resource.ckan_id,
        resource=resource.name,
        to=[user.email],
        username=user.username)


# Pour demander la création d'un territoire de compétence
def send_mail_asking_for_jurisdiction_creation(user, jurisdiction, organisation, url):
    JurisdictionCommune = apps.get_model(
        app_label='idgo_admin', model_name='JurisdictionCommune')
    communes = [
        instance.commune for instance
        in JurisdictionCommune.objects.filter(jurisdiction=jurisdiction)]
    return sender(
        'ask_for_jursidiction_creation',
        # bcc=[user.email],
        full_name=user.get_full_name(),
        name=jurisdiction.name,
        code=jurisdiction.code,
        communes=','.join([commune.code for commune in communes]),
        user_email=user.email,
        url=url,
        organisation=organisation.name,
        organisation_pk=organisation.pk,
        to=get_admins_mails(crige=True),
        username=user.username)


EXTRACTOR_URL = settings.EXTRACTOR_URL


# Pour retourner le résultat d'une extraction
def send_extraction_successfully_mail(user, instance):
    return sender(
        'data_extraction_successfully',
        full_name=user.get_full_name(),
        title=instance.target_object.__str__(),
        to=[user.email],
        url=urljoin(EXTRACTOR_URL, 'jobs/{}/download'.format(instance.uuid)),
        username=user.username)


# Pour informer de l'échec d'une extraction
def send_extraction_failure_mail(user, instance):
    return sender(
        'data_extraction_failure',
        full_name=user.get_full_name(),
        title=instance.target_object.__str__(),
        to=[user.email],
        username=user.username)
