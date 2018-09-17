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
# from django import forms
# from idgo_admin.forms.widgets import MapSelectMultipleWidget
from idgo_admin.models import Category
from idgo_admin.models import Financier
from idgo_admin.models import Granularity
from idgo_admin.models import Jurisdiction
from idgo_admin.models import JurisdictionCommune
from idgo_admin.models import License
from idgo_admin.models import SupportedCrs
from idgo_admin.models import Task


# class JurisdictionCommuneForm(forms.ModelForm):
#
#     class Meta(object):
#         model = JurisdictionCommune
#         fields = '__all__'
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.fields['commune'].widget = MapSelectMultipleWidget()


class JurisdictionCommuneTabularInline(admin.TabularInline):
    can_delete = True
    can_order = True
    extra = 0
    fields = ('commune', 'name', 'code_insee')
    model = JurisdictionCommune
    readonly_fields = ('name', 'code_insee',)
    verbose_name_plural = 'Communes rattachées au territoire de compétence'
    verbose_name = 'Commune rattachée au territoire de compétence'

    def name(self, obj):
        return obj.commune.name
    name.short_description = 'Nom'

    def code_insee(self, obj):
        return obj.commune.pk
    code_insee.short_description = 'Code INSEE'


class JurisdictionCommuneTabularInlineReader(JurisdictionCommuneTabularInline):
    fields = ('name', 'code_insee')
    readonly_fields = ('name', 'code_insee')


class JurisdictionCommuneTabularInlineAdder(JurisdictionCommuneTabularInline):
    extra = 1
    fields = ('commune',)

    def has_change_permission(self, request, obj=None):
        return False


class JurisdictionAdmin(admin.ModelAdmin):

    list_display = ('name', 'code')
    ordering = ('name',)
    search_fields = ('name', 'commune')
    search_fields = ('name', 'code')
    inlines = (JurisdictionCommuneTabularInlineReader, JurisdictionCommuneTabularInlineAdder)
    # form = JurisdictionCommuneForm

admin.site.register(Jurisdiction, JurisdictionAdmin)


class FinancierAdmin(admin.ModelAdmin):
    ordering = ("name", )
    search_fields = ('name', 'code')


admin.site.register(Financier, FinancierAdmin)


class LicensenAdmin(admin.ModelAdmin):
    ordering = ("title", )


admin.site.register(License, LicensenAdmin)


class CategoryAdmin(admin.ModelAdmin):
    model = Category
    readonly_fields = ('ckan_slug',)
    ordering = ('name',)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super(CategoryAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


admin.site.register(Category, CategoryAdmin)


class SupportedCrsAdmin(admin.ModelAdmin):
    pass


admin.site.register(SupportedCrs, SupportedCrsAdmin)


class TaskAdmin(admin.ModelAdmin):
    list_display = (
        'action',
        'state',
        'starting',
        'end'
        )
    ordering = ('starting', )
    readonly_fields = ('starting', )


admin.site.register(Task, TaskAdmin)


class GranularityAdmin(admin.ModelAdmin):
    pass


admin.site.register(Granularity, GranularityAdmin)
