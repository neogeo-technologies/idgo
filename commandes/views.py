from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.core.exceptions import ValidationError

from .forms import OrderForm

# CKAN_URL = settings.CKAN_URL

# decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


# # Imaginary function to handle an uploaded file.
# from somewhere import handle_uploaded_file # https://docs.djangoproject.com/en/1.11/topics/http/file-uploads/

def get_name(request):
#     # if this is a POST request we need to process the form data
    if request.method == 'POST':
#         # create a form instance and populate it with data from the request:
        form = OrderForm(request.POST)
    #         # check whether it's valid:
        if form.is_valid():
            dpo_cnil = forms.FileField()
            acte_engagement = forms.FileField()

#             recipients = [User.email] #a verifier

#             send.mail(subject, message, sender, recipients) # a completer (https://docs.djangoproject.com/en/1.11/topics/email/)
            
#             return HttpResponseRedirect('/thanks/')

    # if a GET (or any other method) we'll create a blank form
    else:
        form = OrderForm()

    return render(request, 'commandes.html', {'form': form})
