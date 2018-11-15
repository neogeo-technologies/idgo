from django import forms
from django.utils import timezone
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.forms import CustomCheckboxSelectMultiple

from .models import Order


class OrderForm(forms.ModelForm):
    class Meta(object):
        model = Order
        fields = [
            'organisation',
            'dpo_cnil',
            'acte_engagement'
        ]

        organisation = forms.ModelMultipleChoiceField(
            label='Organisation',
            queryset=None,
            required=True,
            to_field_name='pk',
            widget=CustomCheckboxSelectMultiple(
                attrs={'class': 'list-group-checkbox'}))

    def __init__(self, *args, **kwargs):
        '''
        recupere l'identifiant du user depuis view.py pour que l'utilisateur
        ne voie que ses organisations
        '''
        user = kwargs.pop('user', None)
        super(OrderForm, self).__init__(*args, **kwargs)
        self.fields['organisation'].queryset = Organisation.objects.filter(
            id=Profile.objects.get(user=user).organisation_id)

    def clean(self):
        '''
        checks if the user has already ordered files
        (order status = 'validée') in the current year
        '''
        cleaned_data = super(OrderForm, self).clean()

        year = timezone.now().date().year
        organisation = cleaned_data.get("organisation")

        STATUS_CHOICES = (
            (0, "En cours"),
            (1, "Validée"),
            (2, "Refusée"))

        match = Order.objects.filter(
                date__year=year,
                organisation=organisation,
                status=STATUS_CHOICES[1]
                )
        
        er_mess = "Une demande a déjà été approuvée pour l'organisation dans l'année en cours."

        if (match):
            raise forms.ValidationError(er_mess)
        else:
            return cleaned_data
