import hashlib
import random

from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse


# Some metaclasses:


class StaticClass(type):
    def __call__(cls):
        raise TypeError(
                "'{0}' static class is not callable.".format(cls.__qualname__))


class Singleton(type):
    __instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls.__instances:
            cls.__instances[cls] = super().__call__(*args, **kwargs)
        # else:
        #     cls._instances[cls].__init__(*args, **kwargs)
        return cls.__instances[cls]


# Methods:


def send_validation_mail(request, email_user, key):

    from_email = 'idgo@neogeo-technologies.fr'
    subject = 'Validation de votre inscription sur le site IDGO'
    message = '''
Bonjour,

Veuillez valider votre inscription en cliquant sur le lien suivant : {0}

Ceci est un message automatique. Merci de ne pas y répondre.'''.format(
        request.build_absolute_uri(
                    reverse('profiles:confirmation_mail', kwargs={'key': key})))

    send_mail(subject=subject,
              message=message,
              from_email=from_email,
              recipient_list=[email_user])


def send_activation_mail(request, registration, email_admin=settings.ADMIN_EMAIL):

    from_email = 'idgo@neogeo-technologies.fr'
    subject = 'Un nouveau compte sur IDGO attend votre confirmation'
    message = '''
Bonjour,

Un nouvel utilisateur ({username}, {user_mail}) a fait une demande d'inscription aux services IDGO. 
Cliquez sur ce lien pour valider son inscription et activer son compte : {url}

Ceci est un message automatique. Merci de ne pas y répondre.'''.format(
        username=registration.user.username,
        user_mail=registration.user.email,
        url=request.build_absolute_uri(
                    reverse('profiles:activation_admin', kwargs={'key': registration.admin_key})))

    send_mail(subject=subject,
              message=message,
              from_email=from_email,
              recipient_list=[email_admin])


def send_confirmation_mail(email_user):

    from_email = settings.DEFAULT_FROM_EMAIL
    subject = 'Confirmation de votre inscription sur le site IDGO'
    message = '''
Bonjour,

Nous confirmons votre inscription sur le site IDGO.

Ceci est un message automatique. Merci de ne pas y répondre.'''

    send_mail(subject=subject,
              message=message,
              from_email=from_email,
              recipient_list=[email_user])

def send_publish_request(get_current_site, publish_request, email_admin=settings.ADMIN_EMAIL):

    from_email = 'idgo@neogeo-technologies.fr'
    subject = 'Un utilisateur requiert un status de contributeur pour une organisation'
    message = '''
    Bonjour,

    Un nouvel utilisateur ({username}, {user_mail}) a fait une demande de contribution 
    pour l'organisation: {organisation_name}.
    Cliquez sur ce lien pour valider son inscription et activer son compte : {url}

    Ceci est un message automatique. Merci de ne pas y répondre.'''.format(
        username=publish_request.user.username,
        user_mail=publish_request.user.email,
        organisation_name=publish_request.organisation.name,
        url=get_current_site(
            reverse('profiles:publish_request', kwargs={'key': publish_request.publish_request_key})))

    send_mail(subject=subject,
              message=message,
              from_email=from_email,
              recipient_list=[email_admin])

def send_publish_confirmation(publish_request):

    from_email = settings.DEFAULT_FROM_EMAIL #TODO: replace w/ "publish_request.organisation.email"

    subject = 'Confirmation de votre inscription en tant que contributeur pour une nouvelle organisation'
    message = '''
    Bonjour,
    
    Votre demande de contribution pour l'organisation: {organisation_name} à été validé.
    
    Ceci est un message automatique. Merci de ne pas y répondre.'''.format(
        organisation_name=publish_request.organisation.name)

    send_mail(subject=subject,
              message=message,
              from_email=from_email,
              recipient_list=[publish_request.user.email])