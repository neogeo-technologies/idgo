from django.conf import settings
from django.core.mail import EmailMessage
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .forms import OrderForm
from .models import Order

# CKAN_URL = settings.CKAN_URL

decorators = [login_required(login_url=settings.LOGIN_URL)]

TODAY = timezone.now().date()


@login_required(login_url=settings.LOGIN_URL)
def upload_file(request):
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = OrderForm(request.POST, request.FILES, user=request.user)
    #         # check whether it's valid:
        if form.is_valid():
            order = form.save(commit=False)
            # peuplement de l'instance applicant du modèle form (= user_id)
            order.applicant = request.user
            order.save()

            # send mail
            admin_email = ['ameillet@neogeo.fr']  # ['support.cadastre@crige-paca.org']
            recipients = ['ameillet@neogeo.fr']  # [request.user.email]
            sender = 'ameillet@neogeo.fr'  # no-reply email ? idgo@neogeo-technologies.fr
            subject = "Confirmation d'envoi de commande de fichiers fonciers"
            message = ("L'instruction de votre commande est en cours. \n"
            'Récapitulatif :\n * Nom: ' + request.user.last_name +
            "\n * Prénom: " + request.user.first_name +
            "\n * courriel: " + request.user.email +
            "\n * date: " + TODAY.strftime('%d/%m/%Y') + "\n")

            message_admin = " \nlien de validation : \n"  # a completer

            # mail utilisateur
            msg = EmailMessage(
                subject=subject,
                body=message,
                from_email=sender,
                to=recipients)

            orderFiltered = Order.objects.get(id=order.pk)
            media = settings.MEDIA_ROOT  # MEDIA_URL 

            # attach two files
            msg.attach_file(media+str(orderFiltered.dpo_cnil))
            msg.attach_file(media+str(orderFiltered.acte_engagement))

            msg.send()

            # mail admin
            msg_admin = EmailMessage(
                subject=subject,
                body=message + message_admin,
                from_email=sender,
                to=admin_email)
            
            # attach two files
            msg_admin.attach_file(media+str(orderFiltered.dpo_cnil))
            msg_admin.attach_file(media+str(orderFiltered.acte_engagement))

            msg_admin.send()

            # page de confirmation
            messageOrder = ("Votre commande de fichiers fonciers "
                            'a bien été envoyée.'
                            ' Vous recevrez un e-mail récapitulatif '
                            "d'ici quelques minutes. ")

            status = 200
            
            return render(request, 'idgo_admin/message.html',
                        {'message': messageOrder}, status=status)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = OrderForm(user=request.user)
    return render(request, 'commandes.html', {'form': form})
