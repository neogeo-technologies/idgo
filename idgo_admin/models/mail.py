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


from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.core.mail import get_connection
from django.core.mail.message import EmailMultiAlternatives
from django.core.mail import send_mail
from django.urls import reverse
from idgo_admin.utils import PartialFormatter
from urllib.parse import urljoin


class Mail(models.Model):

    template_name = models.CharField(
        verbose_name='Nom du model du message',
        primary_key=True, max_length=255)

    subject = models.CharField(
        verbose_name='Objet', max_length=255, blank=True, null=True)

    message = models.TextField(
        verbose_name='Corps du message', blank=True, null=True)

    from_email = models.EmailField(
        verbose_name='Adresse expediteur',
        default=settings.DEFAULT_FROM_EMAIL)

    class Meta(object):
        verbose_name = 'e-mail'
        verbose_name_plural = 'e-mails'

    def __str__(self):
        return self.template_name

    ## TODO Factoriser les classmethod

    @classmethod
    def superuser_mails(cls, receip_list):
        receip_list = receip_list + [
            usr.email for usr in User.objects.filter(
                is_superuser=True, is_active=True)]
        return receip_list

    @classmethod
    def admin_mails(cls, receip_list):
        Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')

        receip_list = receip_list + [
            p.user.email for p in Profile.objects.filter(
                is_active=True, is_admin=True)]
        return receip_list

    @classmethod
    def referents_mails(cls, receip_list, organisation):
        LiaisonsReferents = apps.get_model(app_label='idgo_admin', model_name='LiaisonsReferents')

        receip_list = receip_list + [
            lr.profile.user.email for lr in LiaisonsReferents.objects.filter(
                organisation=organisation, validated_on__isnull=False)]
        return receip_list

    @classmethod
    def receivers_list(cls, organisation=None):
        receip_list = []
        receip_list = cls.superuser_mails(receip_list)
        receip_list = cls.admin_mails(receip_list)
        if organisation:
            receip_list = cls.referents_mails(receip_list, organisation)

        # Pour retourner une liste de valeurs uniques
        return list(set(receip_list))

    @classmethod
    def send_credentials_user_creation_admin(cls, cleaned_data):
        msg_on_create = """Bonjour, {last_name}, {first_name},
Un compte vous a été créé par les services d'administration sur la plateforme Datasud .
+ Identifiant de connexion: {username}

Veuillez initializer votre mot de passe en suivant le lien suivant.
+ Url de connexion: {url}

Ce message est envoyé automatiquement. Veuillez ne pas répondre. """
        sub_on_create = "Un nouveau compte vous a été crée sur la plateforme Datasud"

        mail_template, created = cls.objects.get_or_create(
            template_name='credentials_user_creation_admin',
            defaults={
                'message': msg_on_create,
                'subject': sub_on_create})

        fmt = PartialFormatter()
        data = {'first_name': cleaned_data.get('first_name'),
                'last_name': cleaned_data.get('last_name').upper(),
                'username': cleaned_data.get('username'),
                'url': cleaned_data.get('url')}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject, message=message,
                  from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[cleaned_data.get('email')])

    @classmethod
    def validation_user_mail(cls, request, action):

        user = action.profile.user
        mail_template = Mail.objects.get(template_name='validation_user_mail')
        from_email = mail_template.from_email
        subject = mail_template.subject

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirmation_mail',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=subject, message=message,
                  from_email=from_email, recipient_list=[user.email])

    @classmethod
    def confirmation_user_mail(cls, user):
        """E-mail de confirmation.

        E-mail confirmant la creation d'une nouvelle organisation
        suite à une inscription.
        """
        mail_template = \
            Mail.objects.get(template_name='confirmation_user_mail')

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])

    @classmethod
    def confirm_new_organisation(cls, request, action):  # A revoir complétement !
        """E-mail de validation.

        E-mail permettant de valider la création d'une nouvelle organisation
        suite à une inscription.
        """
        user = action.profile.user
        organisation = action.organisation
        website = organisation.website or '- adresse url manquante -'
        mail_template = \
            Mail.objects.get(template_name='confirm_new_organisation')

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_new_orga',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list(organisation))

    @classmethod
    def confirm_rattachement(cls, request, action):

        user = action.profile.user
        organisation = action.profile.organisation
        website = organisation.website or '- adresse url manquante -'
        mail_template = Mail.objects.get(template_name='confirm_rattachement')

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_rattachement',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list(organisation))

    @classmethod
    def confirm_updating_rattachement(cls, request, action):

        user = action.profile.user
        organisation = action.organisation
        website = organisation.website or '- adresse url manquante -'
        mail_template = \
            Mail.objects.get(template_name="confirm_updating_rattachement")

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_rattachement',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list(organisation))

    @classmethod
    def confirm_referent(cls, request, action):
        user = action.profile.user
        organisation = action.organisation
        website = organisation.website or '- adresse url manquante -'
        mail_template = \
            Mail.objects.get(template_name="confirm_referent")

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_referent',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list())

    @classmethod
    def confirm_contribution(cls, request, action):

        user = action.profile.user
        organisation = action.organisation
        website = organisation.website or '- adresse url manquante -'
        mail_template = \
            Mail.objects.get(template_name="confirm_contribution")

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'user_mail': user.email,
                'organisation_name': organisation.name,
                'website': website,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:confirm_contribution',
                            kwargs={'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=cls.receivers_list(organisation))

    @classmethod
    def affiliate_confirmation_to_user(cls, profile):

        mail_template = \
            Mail.objects.get(template_name="affiliate_confirmation_to_user")

        fmt = PartialFormatter()
        data = {'organisation_name': profile.organisation.name}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[profile.user.email])

    @classmethod
    def confirm_contrib_to_user(cls, action):

        organisation = action.organisation
        user = action.profile.user

        mail_template = \
            Mail.objects.get(template_name="confirm_contrib_to_user")

        fmt = PartialFormatter()
        data = {'organisation_name': organisation.name}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])

    @classmethod
    def conf_deleting_dataset_res_by_user(cls, user, dataset=None, resource=None):

        fmt = PartialFormatter()
        if dataset:
            mail_template = \
                Mail.objects.get(template_name="conf_deleting_dataset_by_user")

            data = {'dataset_name': dataset.name}

        elif resource:
            mail_template = \
                Mail.objects.get(template_name="conf_deleting_res_by_user")

            data = {'dataset_name': dataset.name,
                    'resource_name': resource.name}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])

    @classmethod
    def conf_deleting_profile_to_user(cls, user_copy):

        mail_template = \
            Mail.objects.get(template_name="conf_deleting_profile_to_user")

        fmt = PartialFormatter()
        data = {'first_name': user_copy["first_name"],
                'last_name': user_copy["last_name"],
                'username': user_copy["username"]}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user_copy["email"]])

    @classmethod
    def send_reset_password_link_to_user(cls, request, action):

        mail_template = \
            Mail.objects.get(template_name="send_reset_password_link_to_user")
        user = action.profile.user

        fmt = PartialFormatter()
        data = {'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'url': request.build_absolute_uri(
                    reverse('idgo_admin:password_manager',
                            kwargs={'process': 'reset', 'key': action.key}))}

        message = fmt.format(mail_template.message, **data)
        send_mail(subject=mail_template.subject,
                  message=message,
                  from_email=mail_template.from_email,
                  recipient_list=[user.email])
    ##

    @classmethod
    def creating_a_dataset(cls, profile, instance):
        Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
        bcc = [p.user.email for p in Profile.get_admin()]
        cls.sender('creating_a_dataset',
                   to=[profile.user.email], bcc=bcc,
                   full_name=profile.user.get_full_name(),
                   username=profile.user.username,
                   resource=instance.name)

    @classmethod
    def updating_a_dataset(cls, profile, instance):
        Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
        bcc = [p.user.email for p in Profile.get_admin()]
        cls.sender('updating_a_dataset',
                   to=[profile.user.email], bcc=bcc,
                   full_name=profile.user.get_full_name(),
                   username=profile.user.username,
                   resource=instance.name)

    @classmethod
    def deleting_a_dataset(cls, profile, instance):
        Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
        bcc = [p.user.email for p in Profile.get_admin()]
        cls.sender('deleting_a_dataset',
                   to=[profile.user.email], bcc=bcc,
                   full_name=profile.user.get_full_name(),
                   username=profile.user.username,
                   resource=instance.name)

    @classmethod
    def creating_a_resource(cls, profile, instance):
        Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
        bcc = [p.user.email for p in Profile.get_admin()]
        cls.sender('creating_a_resource',
                   to=[profile.user.email], bcc=bcc,
                   full_name=profile.user.get_full_name(),
                   username=profile.user.username,
                   resource=instance.name,
                   dataset=instance.dataset.name)

    @classmethod
    def updating_a_resource(cls, profile, instance):
        Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
        bcc = [p.user.email for p in Profile.get_admin()]
        cls.sender('updating_a_resource',
                   to=[profile.user.email], bcc=bcc,
                   full_name=profile.user.get_full_name(),
                   username=profile.user.username,
                   resource=instance.name,
                   dataset=instance.dataset.name)

    @classmethod
    def deleting_a_resource(cls, profile, instance):
        Profile = apps.get_model(app_label='idgo_admin', model_name='Profile')
        bcc = [p.user.email for p in Profile.get_admin()]
        cls.sender('deleting_a_resource',
                   to=[profile.user.email], bcc=bcc,
                   full_name=profile.user.get_full_name(),
                   username=profile.user.username,
                   resource=instance.name,
                   dataset=instance.dataset.name)

    @classmethod
    def data_extraction_successfully(cls, profile, instance):
        # bcc = [p.user.email for p in Profile.get_admin()]
        url = urljoin(
            settings.EXTRACTOR_URL, 'job/{}/download'.format(instance.uuid))
        cls.sender('data_extraction_successfully',
                   to=[profile.user.email],
                   # bcc=bcc,
                   full_name=profile.user.get_full_name(),
                   username=profile.user.username,
                   url=url,
                   dataset=instance.layer.resource.dataset.name)

    @classmethod
    def data_extraction_failure(cls, profile, instance):
        # bcc = [p.user.email for p in Profile.get_admin()]
        cls.sender('data_extraction_failure',
                   to=[profile.user.email],
                   # bcc=bcc,
                   full_name=profile.user.get_full_name(),
                   username=profile.user.username,
                   resource=instance.name,
                   dataset=instance.dataset.name)

    @classmethod
    def sender(cls, template_name, to, cc=None, bcc=None, **kvp):
        try:
            tmpl = Mail.objects.get(template_name=template_name)
        except Mail.DoesNotExist:
            return False

        subject = tmpl.subject
        body = PartialFormatter().format(tmpl.message, **kvp)
        from_email = tmpl.from_email
        connection = get_connection(fail_silently=False)

        mail = EmailMultiAlternatives(
            subject=subject, body=body,
            from_email=from_email, to=to,
            cc=cc, bcc=bcc, connection=connection)
        return mail.send()
