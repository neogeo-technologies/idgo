import hashlib
import random

from django.http import JsonResponse
from django.core.mail import send_mail


def sendmail(request, email_user):
    error = None
    # Creer mail de validation avec url + hash
    salt = hashlib.sha1(str(random.random()).encode('utf-8')).hexdigest()[:5].encode('utf-8')
    key = hashlib.sha1(salt + email_user).hexdigest()
    url = "{}{}".format(request.build_absolute_uri(), key)
    try:
        send_mail(subject="Validation",
                  message="Validation inscription IDGO: {}".format(url),
                  from_email="cbenhabib@neogeo.fr",
                  recipient_list=[email_user])
    except:
        error = JsonResponse(data={"error": "Echec de l'envoi de l'email de validation"},
                             status=400)
    return key, error