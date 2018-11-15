from django.conf import settings
from django.core.mail import EmailMessage
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .forms import OrderForm

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
            order.applicant = request.user
            order.save()

            # send mail
            recipients = ['ameillet@neogeo.fr']#[request.user.email]
            sender = 'ameillet@neogeo.fr'
            subject = "Confirmation d'envoi de commande de fichiers fonciers"
            message = ("L'instruction de votre commande est en cours. " +
            'recapitulatif : Nom: ' + request.user.last_name +
            "\n" + "Prénom: " + request.user.first_name +
            "\n" + "courriel: " + recipients)
            #"\n date: " + TODAY.strftime('%d/%m/%Y'))

            msg=EmailMessage(
                subject=subject,
                body=message,
                from_email=sender,
                to=recipients)
            # attach two files
            msg.attach_file(settings.MEDIA_URL+OrderForm.get("dpo_cnil"))
            msg.attach_file(settings.MEDIA_URL+OrderForm.get("acte_engagement"))

            # page de confirmation
            messageOrder = ("Votre commande de fichiers fonciers"
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
