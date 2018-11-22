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

from commandes.models import Order


class CustomClearableFileInput(forms.ClearableFileInput):
    template_name = 'idgo_admin/widgets/file_drop_zone.html'


class OrderForm(forms.ModelForm):

    organisation = forms.ModelChoiceField(
        label='Organisation*',
        queryset=None,
        required=True,
        empty_label='Sélectionnez une organisation')

    dpo_cnil = forms.FileField(
        label='DPO CNIL*',
        required=True,
        widget=CustomClearableFileInput(attrs={'value': None}))

    acte_engagement = forms.FileField(
        label="Acte d'engagement*",
        required=True,
        widget=CustomClearableFileInput(attrs={'value': None}))

    class Meta(object):
        model = Order
        fields = [
            'organisation',
            'dpo_cnil',
            'acte_engagement']

    def __init__(self, *args, user=None, **kwargs):
        """
        recupere l'identifiant du user depuis view.py pour que l'utilisateur
        ne voie que ses organisations
        """
        super().__init__(*args, **kwargs)
        self.fields['organisation'].queryset = Organisation.objects.filter(
            id=Profile.objects.get(user=user).organisation_id)

    def clean(self):
        """
        checks if the user has already ordered files
        (order status = 'validée') in the current year
        """
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
