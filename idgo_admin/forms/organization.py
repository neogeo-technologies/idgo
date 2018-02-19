from django import forms
from idgo_admin.forms import common_fields
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
    name = common_fields.ORGANISATION_NAME
    logo = common_fields.ORGANISATION_LOGO
    address = common_fields.ADDRESS
    city = common_fields.CITY
    postcode = common_fields.POSTCODE
    org_phone = common_fields.PHONE
    email = common_fields.EMAIL
    website = common_fields.WEBSITE
    description = common_fields.DESCRIPTION
    jurisdiction = common_fields.JURISDICTION
    organisation_type = common_fields.ORGANISATION_TYPE
    license = common_fields.LICENSE

    # Extended fields
    rattachement_process = common_fields.MEMBER
    contributor = common_fields.CONTRIBUTOR
    referent = common_fields.REFERENT

    def __init__(self, *args, **kwargs):
        self.include_args = kwargs.pop('include', {})
        self.extended = self.include_args.get('extended', False)
        super().__init__(*args, **kwargs)

        if not self.extended:
            for item in self.Meta.extended_fields:
                self.fields[item].widget = forms.HiddenInput()

    def clean(self):
        return self.cleaned_data
