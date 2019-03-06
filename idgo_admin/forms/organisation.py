# Copyright (c) 2017-2019 Datasud.
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
from idgo_admin.ckan_module import CkanBaseHandler
from idgo_admin.exceptions import CkanBaseError
from idgo_admin.forms import AddressField
from idgo_admin.forms import CityField
from idgo_admin.forms import ContributorField
from idgo_admin.forms import CustomCheckboxSelectMultiple
from idgo_admin.forms import DescriptionField
from idgo_admin.forms import EMailField
from idgo_admin.forms import JurisdictionField
from idgo_admin.forms import LicenseField
from idgo_admin.forms import MemberField
from idgo_admin.forms import OrganisatioLegalNameField
from idgo_admin.forms import OrganisationLogoField
from idgo_admin.forms import OrganisationTypeField
from idgo_admin.forms import PhoneField
from idgo_admin.forms import PostcodeField
from idgo_admin.forms import ReferentField
from idgo_admin.forms import WebsiteField
from idgo_admin.models import Jurisdiction
from idgo_admin.models import Organisation
from idgo_admin.models import RemoteCkan


class OrganisationForm(forms.ModelForm):

    class Meta(object):
        model = Organisation

        organisation_fields = (
            'address',
            'city',
            'description',
            'email',
            'jurisdiction',
            'license',
            'logo',
            'legal_name',
            'organisation_type',
            'phone',
            'postcode',
            'website')

        extended_fields = (
            'contributor_process',
            'rattachement_process',
            'referent_process')

        fields = organisation_fields + extended_fields

    # Organisation fields
    legal_name = OrganisatioLegalNameField(required=True)
    logo = OrganisationLogoField()
    address = AddressField()
    city = CityField()
    postcode = PostcodeField()
    org_phone = PhoneField()
    email = EMailField()
    website = WebsiteField()
    description = DescriptionField()
    jurisdiction = JurisdictionField()
    organisation_type = OrganisationTypeField()
    license = LicenseField()

    # Extended fields
    rattachement_process = MemberField()
    contributor_process = ContributorField()
    referent_process = ReferentField()

    def __init__(self, *args, **kwargs):
        self.include_args = kwargs.pop('include', {})
        self.extended = self.include_args.get('extended', False)
        self.instance = kwargs.get('instance', None)
        self.user = self.include_args.get('user')

        super().__init__(*args, **kwargs)

        if not self.extended:
            for item in self.Meta.extended_fields:
                self.fields[item].widget = forms.HiddenInput()

        if self.instance and self.instance.logo:
            self.fields['logo'].widget.attrs['value'] = self.instance.logo.url

        if self.instance and not self.user.profile.is_crige_admin:
            self.fields['jurisdiction'].queryset = \
                Jurisdiction.objects.filter(pk__in=self.instance.jurisdiction and [self.instance.jurisdiction.pk] or [])
            self.fields['jurisdiction'].widget.attrs['disabled'] = 'disabled'
            self.fields['jurisdiction'].widget.attrs['class'] = 'disabled'

    def clean(self):
        if self.instance and not self.user.profile.is_crige_admin:
            self.cleaned_data['jurisdiction'] = self.instance.jurisdiction
        return self.cleaned_data


class RemoteCkanForm(forms.ModelForm):

    class Meta(object):
        model = RemoteCkan
        fields = (
            'url',
            'sync_with',
            'sync_frequency')

    url = forms.URLField(
        error_messages={'invalid': "L'adresse URL est erronée."},
        label='URL du catalogue CKAN à synchroniser',
        required=True,
        widget=forms.TextInput(attrs={'placeholder': "https://demo.ckan.org"}))

    sync_with = forms.MultipleChoiceField(
        label='Organisations à synchroniser',
        choices=(),  # ckan api -> list_organisations
        required=False,
        widget=CustomCheckboxSelectMultiple(
            attrs={'class': 'list-group-checkbox'}))

    sync_frequency = forms.ChoiceField(
        label='Fréquence de synchronisation',
        choices=Meta.model.FREQUENCY_CHOICES,
        initial='never',
        required=True)

    def __init__(self, *args, **kwargs):
        self.cleaned_data = {}
        super().__init__(*args, **kwargs)

        instance = kwargs.get('instance', None)
        if instance and instance.url:
            self.fields['url'].widget.attrs['readonly'] = True
            # Récupérer la liste des organisations
            try:
                with CkanBaseHandler(instance.url) as ckan:
                    organisations = ckan.get_all_organisations(
                        all_fields=True, include_dataset_count=True)
            except CkanBaseError as e:
                self.add_error('url', e.message)
            else:
                self.fields['sync_with'].choices = (
                    (organisation['name'], '{} ({})'.format(
                        organisation['display_name'],
                        organisation.get(
                            'package_count',
                            organisation.get('packages', None))))
                    for organisation in organisations)
        else:
            self.fields['sync_with'].widget = forms.HiddenInput()
            self.fields['sync_frequency'].widget = forms.HiddenInput()
