import smtplib
import hashlib
import random

from django.core.mail import send_mail


def sendmail(email_user):

    # Creer mail de validation avec url + hash
    salt = hashlib.sha1(str(random.random()).encode('utf-8')).hexdigest()[:5].encode('utf-8')
    key = hashlib.sha1(salt + email_user).hexdigest()

    try:
        send_mail(subject="Confirmation",
                  message="hash de validation d'adresse mail. {}".format(key),
                  from_email="cbenhabib@neogeo.fr",
                  recipient_list=[email_user])
    except:
        return False
    return True