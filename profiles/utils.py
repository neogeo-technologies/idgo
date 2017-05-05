import hashlib
import random

from django.http import JsonResponse
from django.core.mail import send_mail


def create_activation_key(email_user):
    salt = hashlib.sha1(str(random.random()).encode('utf-8')).hexdigest()[:5].encode('utf-8')
    return hashlib.sha1(salt + bytes(email_user, 'utf-8')).hexdigest()


def sendmail(request, email_user, key):

    url = "{0}{1}".format(request.build_absolute_uri(), key)

    from_email = 'cbenhabib@neogeo.fr'
    subject = 'Validation de votre inscription sur le site IDGO.'
    message = 'Bonjour, \n\n' \
              'Veuillez valider votre inscription en cliquant sur le lien ' \
              'suivant : {0}'.format(url)

    try:
        send_mail(subject=subject, message=message,
                  from_email=from_email, recipient_list=[email_user])
    except:
        raise
