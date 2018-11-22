# Copyright (c) 2017-2018 Datasud.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from django import forms
from django.utils import timezone
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.forms import CustomCheckboxSelectMultiple

from commandes.models import Order


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
            # empty_label=None  # could prevent the ---- 
            # https://docs.djangoproject.com/en/2.1/ref/forms/fields/#django.forms.ModelChoiceField
            # causes __init__ error
            # to_field_name='pk',
            widget=CustomCheckboxSelectMultiple(
                attrs={'class': 'list-group-checkbox'}))

        status = forms.ChoiceField(choices=Order.STATUS_CHOICES)

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

        match = Order.objects.filter(
                date__year=year,
                organisation=organisation,
                status=1
                )

        er_mess = ("Une demande a déjà été approuvée pour cette organisation"
                    " dans l'année civile en cours.")

        if (match):
            # self.add_error('__all__',er_mess)
            raise forms.ValidationError(er_mess)
        else:
            return cleaned_data
