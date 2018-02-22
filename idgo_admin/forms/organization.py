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
from idgo_admin.forms import AddressField
from idgo_admin.forms import CityField
from idgo_admin.forms import ContributorField
from idgo_admin.forms import DescriptionField
from idgo_admin.forms import EMailField
from idgo_admin.forms import JurisdictionField
from idgo_admin.forms import LicenseField
from idgo_admin.forms import MemberField
from idgo_admin.forms import OrganisatioNameField
from idgo_admin.forms import OrganisationLogoField
from idgo_admin.forms import OrganisationTypeField
from idgo_admin.forms import PhoneField
from idgo_admin.forms import PostcodeField
from idgo_admin.forms import ReferentField
from idgo_admin.forms import WebsiteField
from idgo_admin.models import Organisation


class OrganizationForm(forms.ModelForm):

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
            'name',
            'organisation_type',
            'org_phone',
            'postcode',
            'website')

        extended_fields = (
            'contributor_process',
            'rattachement_process',
            'referent_process')

        fields = organisation_fields + extended_fields

    # Organisation fields
    name = OrganisatioNameField()
    logo = OrganisationLogoField()
    address = AddressField()
    city = CityField()
    postcode = PostcodeField()
    org_phone = PhoneField()
    email = EMailField(required=False)
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
        super().__init__(*args, **kwargs)

        if not self.extended:
            for item in self.Meta.extended_fields:
                self.fields[item].widget = forms.HiddenInput()

    def clean(self):
        return self.cleaned_data
