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


from django.contrib import admin
from django.contrib.auth.models import User
from django import forms
from django.forms.models import BaseInlineFormSet
from django.utils.text import slugify
from idgo_admin import logger
from idgo_admin.models import Dataset
from idgo_admin.models import Profile
from idgo_admin.models import Resource
from idgo_admin.models import ResourceFormats


def synchronize(modeladmin, request, queryset):
    for dataset in queryset:
        logger.info('Force save dataset {pk}: {slug}'.format(
            slug=dataset.slug or slugify(dataset.title), pk=dataset.pk))
        try:
            dataset.save(current_user=None, synchronize=True)
        except Exception as e:
            logger.error(e)
            continue


class ResourceFormatsAdmin(admin.ModelAdmin):
    ordering = ['extension']

    def __init__(self, *args, **kwargs):
        super(ResourceFormatsAdmin, self).__init__(*args, **kwargs)

    class Meta(object):
        model = Resource


admin.site.register(ResourceFormats, ResourceFormatsAdmin)


class ResourceInlineFormset(BaseInlineFormSet):

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)
        for form in self.forms:
            is_sync_requested = form.cleaned_data.get('synchronisation')
            frequency_not_set = form.cleaned_data.get('sync_frequency') == 'never'
            if is_sync_requested and frequency_not_set:
                raise forms.ValidationError((
                    'Une période de synchronisation est nécessaire si vous '
                    'choisissez de sychroniser les données distantes'))


class ResourceInline(admin.StackedInline):
    model = Resource
    formset = ResourceInlineFormset
    extra = 0
    can_delete = True
    fieldsets = [
        ('Synchronisation distante', {
            'classes': ['collapse'],
            'fields': [
                'synchronisation',
                'sync_frequency']}),
        (None, {
            'classes': ['wide'],
            'fields': [
                ('title', 'description', ),
                ('referenced_url', 'dl_url', 'up_file'),
                'lang',
                'format_type',
                'restricted_level',
                'profiles_allowed',
                'organisations_allowed',
                'bbox',
                'geo_restriction',
                'created_on',
                'last_update']})]


class MyDataSetForm(forms.ModelForm):

    class Meta(object):
        model = Dataset
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['organisation'].required = True
        self.fields['editor'].queryset = User.objects.filter(
            profile__in=Profile.objects.all(),
            is_active=True).order_by('username')


class DatasetAdmin(admin.ModelAdmin):
    list_display = ['title', 'name_editor', 'nb_resources']
    inlines = [ResourceInline]
    ordering = ['title']
    form = MyDataSetForm
    can_add_related = True
    can_delete_related = True
    readonly_fields = ['ckan_id', 'slug', 'geonet_id']
    search_fields = ['title', 'editor__username']
    actions = [synchronize]

    synchronize.short_description = 'Forcer la synchronisation des jeux de données'

    def nb_resources(self, obj):
        return Resource.objects.filter(dataset=obj).count()

    nb_resources.short_description = 'Nombre de ressources'

    def name_editor(self, obj):
        first_name = obj.editor.first_name
        last_name = obj.editor.last_name
        return '{} {}'.format(first_name, last_name.upper())

    name_editor.short_description = 'Producteur (propriétaire)'


admin.site.register(Dataset, DatasetAdmin)
