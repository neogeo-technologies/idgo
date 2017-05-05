from django.core.mail import send_mail


# Some metaclasses:


class StaticClass(type):
    def __call__(cls):
        raise TypeError('\'{0}\' static class is not callable.'.format(
                                                            cls.__qualname__))


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

    url = "{0}{1}".format(request.build_absolute_uri(), key)

    from_email = 'cbenhabib@neogeo.fr'
    subject = 'Validation de votre inscription sur le site IDGO.'
    message = '''
Bonjour,

Veuillez valider votre inscription en cliquant sur le lien suivant : {0}

Ceci est un message automatique. Merci de ne pas y repondre.'''.format(url)

    send_mail(subject=subject,
              message=message,
              from_email=from_email,
              recipient_list=[email_user])
