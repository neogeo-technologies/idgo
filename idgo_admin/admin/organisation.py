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


from django.contrib import admin
from django.contrib.gis import admin as geo_admin
from django import forms
from idgo_admin.models import Organisation
from idgo_admin.models import OrganisationType


geo_admin.GeoModelAdmin.default_lon = 160595
geo_admin.GeoModelAdmin.default_lat = 5404331
geo_admin.GeoModelAdmin.default_zoom = 14


class OrganisationForm(forms.ModelForm):

    class Meta(object):
        model = Organisation
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].initial = True


class OrganisationAdmin(geo_admin.OSMGeoAdmin):

    list_display = ('name', 'organisation_type')
    search_fields = ('name', )
    list_filter = ('organisation_type',)
    ordering = ('name',)
    readonly_fields = ('ckan_slug', )
    form = OrganisationForm

    def get_form(self, request, obj=None, **kwargs):
        if not request.user.profile.is_crige_admin:
            self.form._meta.exclude = ('is_crige_partner',)
        return super().get_form(request, obj, **kwargs)


admin.site.register(Organisation, OrganisationAdmin)


class OrganisationTypeAdmin(admin.ModelAdmin):
    ordering = ('name', )
    search_fields = ('name', 'code')


admin.site.register(OrganisationType, OrganisationTypeAdmin)
