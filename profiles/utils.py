import smtplib

from django.core.mail import send_mail


def sendmail(email_user):

    try:
        send_mail(subject="Confirmation",
                  message="hash de validation d'adresse mail.",
                  from_email="cbenhabib@neogeo.fr",
                  recipient_list=[email_user])

    except:
        return False
    return True