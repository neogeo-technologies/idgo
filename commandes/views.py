from django.conf import settings
from django.core.mail import EmailMessage
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from idgo_admin.models.mail import sender as mail_sender


from .forms import OrderForm
from .models import Order

# CKAN_URL = settings.CKAN_URL

decorators = [login_required(login_url=settings.LOGIN_URL)]

TODAY = timezone.now().date()

CADASTRE_CONTACT_EMAIL = settings.CADASTRE_CONTACT_EMAIL


@login_required(login_url=settings.LOGIN_URL)
def upload_file(request):

    user = request.user

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = OrderForm(request.POST, request.FILES, user=request.user)

        # check whether it's valid:
        if form.is_valid():
            order = form.save(commit=False)
            # peuplement de l'instance applicant du modèle form (= user_id)
            order.applicant = request.user
            order.save()

            attach_files = [
                order.dpo_cnil.file.name,
                order.acte_engagement.file.name]

            mail_kwargs = {
                'attach_files': attach_files,
                'full_name': user.get_full_name(),
                'last_name': user.last_name,
                'first_name': user.first_name,
                'date': TODAY.strftime('%d/%m/%Y'),
                'email': user.email}

            mail_sender('cadastre_order', to=[user.email], **mail_kwargs)
            mail_sender(
                'confirm_cadastre_order', to=CADASTRE_CONTACT_EMAIL, **mail_kwargs)

            # page de confirmation
            messageOrder = ("Votre commande de fichiers fonciers "
                            'a bien été envoyée.'
                            ' Vous recevrez un e-mail récapitulatif '
                            "d'ici quelques minutes. ")

            return render(request, 'idgo_admin/message.html',
                          {'message': messageOrder})

    # if a GET (or any other method) we'll create a blank form
    else:
        form = OrderForm(user=request.user)
    return render(request, 'commandes.html', {'form': form})
