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
        request.build_absolute_uri(reverse('activation', kwargs={'key': key})))

    send_mail(subject=subject,
              message=message,
              from_email=from_email,
              recipient_list=[email_user])


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