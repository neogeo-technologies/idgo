from django import forms

from .models import Order

STATUS_CHOICES = (
    (1, "En cours"),
    (2, "Validée"),
    (3, "Refusée")
)

class OrderForm(forms.ModelForm):
    class Meta(object):
        model = Order
        fields = [
            # 'applicant',
            # 'date',
            'dpo_cnil',
            'acte_engagement'
        ]


    # applicant = forms.CharField(label='nom utilisateur', max_length=100)# à recupérer automatiquement ?
    # date = forms.DateField('Date de la demande', disabled =True)
    # dpo_cnil = forms.FileField()
    # acte_engagement = forms.FileField()


    # def clean(self):
    #     '''
    #     checks if the user has already ordered files (order status = 'validée') in the current year
    #     '''
    #     cleaned_data = super(OrderForm, self).clean()
        
    #     year = cleaned_data.get(year=date.year)# possibilité de récuperer la date depuis le modèle ?
    #     organisation = Order.object.get # comment récuperer l'organisation ? (table User ?)

    #     try:
    #         match = Order.objects.get(year=year)
    #     except User.DoesNotExist:
    #         return 
        
    #     raise forms.ValidationError("Une demande a déjà été approuvée pour l'organisation dans l'année en cours.")
    