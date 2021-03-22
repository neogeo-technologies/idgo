# Copyright (c) 2017-2021 Neogeo-Technologies.
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


import logging
import re

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib import messages
from django import forms
from django.forms.models import BaseInlineFormSet
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.text import slugify

from taggit.admin import Tag
from taggit.models import TaggedItem

from idgo_admin.ckan_module import CkanBaseError
from idgo_admin.ckan_module import CkanHandler
from idgo_admin.models import Dataset
from idgo_admin.models import Keywords
from idgo_admin.models import Profile
from idgo_admin.models import Resource
from idgo_admin.models import ResourceFormats


logger = logging.getLogger('idgo_admin')


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
    ordering = ('extension',)

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
            frequency_not_set = form.cleaned_data.get(
                'sync_frequency') == 'never'
            if is_sync_requested and frequency_not_set:
                raise forms.ValidationError((
                    "Une période de synchronisation est nécessaire si vous "
                    "choisissez de sychroniser les données distantes"))


class ResourceInline(admin.StackedInline):
    model = Resource
    formset = ResourceInlineFormset
    extra = 0
    can_delete = False
    fieldsets = [
        ('Synchronisation distante', {
            'classes': ['collapse'],
            'fields': [
                'synchronisation',
                'sync_frequency']}
         ),
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
                'last_update']}
         )
    ]
    readonly_fields = ['bbox']


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
        self.fields['keywords'].widget.attrs['style'] = 'width: 612px;'


class DatasetAdmin(admin.ModelAdmin):
    list_display = ['title', 'name_editor', 'nb_resources']
    inlines = [ResourceInline]
    ordering = ['title']
    form = MyDataSetForm
    can_add_related = True
    can_delete_related = True
    readonly_fields = ['ckan_id', 'slug', 'geonet_id', 'bbox']
    search_fields = ['title', 'editor__username']
    actions = [synchronize]

    synchronize.short_description = 'Forcer la synchronisation des jeux de données'

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_delete_permission(self, request, obj=None):
        return False

    def nb_resources(self, obj):
        return Resource.objects.filter(dataset=obj).count()

    nb_resources.short_description = 'Nombre de ressources'

    def name_editor(self, obj):
        first_name = obj.editor.first_name
        last_name = obj.editor.last_name
        return '{} {}'.format(first_name, last_name.upper())

    name_editor.short_description = 'Producteur (propriétaire)'


admin.site.register(Dataset, DatasetAdmin)


class InputFilter(admin.SimpleListFilter):
    template = 'admin/idgo_admin/input_filter.html'

    def message_error(self, request, queryset):
        messages.error(
            request, "Aucune donnée ne correspond à votre requête.")
        return queryset.none()

    def lookups(self, request, model_admin):
        # Nécessaire au rendu de filtre
        return ((),)

    def choices(self, changelist):
        # Si option 'Tous' cochée
        all_choice = next(super().choices(changelist))
        all_choice['query_parts'] = (
            (k, v) for k, v in changelist.get_filters_params().items() if k != self.parameter_name)
        yield all_choice


class KwInputFilter(InputFilter):
    title = "Mots-clés"
    parameter_name = 'slug'

    def queryset(self, request, queryset):

        if self.value() is not None:
            try:
                queryset = queryset.filter(slug__icontains=self.value())
            except Exception:
                return self.message_error(request, queryset)
        return queryset


class NewKeywordForm(forms.ModelForm):

    new_name = forms.CharField(
        max_length=500)

    class Meta(object):
        model = Tag
        fields = ('new_name', )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_name'].required = True
        self.fields['new_name'].label = 'Mot-clé'

    def clean_new_name(self):
        data = self.cleaned_data['new_name'].strip()
        if len(data) < 2:
            raise forms.ValidationError(
                "La taille minimum pour un mot-clé est de 2 caractères.")
        regex = '^[a-zA-Z0-9áàâäãåçéèêëíìîïñóòôöõúùûüýÿæœÁÀÂÄÃÅÇÉÈÊËÍÌÎÏÑÓÒÔÖÕÚÙÛÜÝŸÆŒ\._\-\s]*$'
        if not re.match(regex, data):
            raise forms.ValidationError(
                "Les mots-clés ne peuvent pas contenir de caractères spéciaux.")
        return data


class TaggedItemInline(admin.TabularInline):
    model = TaggedItem
    extra = 0
    can_delete = True
    show_change_link = True
    readonly_fields = (
        'change_link',
        'content_type',
        'object_id',
        )
    fields = (
        'change_link',
        'content_type',
        )

    def has_add_permission(self, request):
        return False

    def change_link(self, obj):
        # Pour le fun
        if obj and obj.content_type.model == 'dataset':
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse('admin:idgo_admin_dataset_change',
                            args=(obj.object_id,),),
                    obj.object_id
                    ))
        return 'N/A'
    change_link.short_description = "Fiche détaillée"


admin.site.unregister(Tag)


class KeywordsAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_filter = (KwInputFilter,)
    actions = ('merge_name',)
    readonly_fields = ('slug',)
    inlines = (TaggedItemInline,)

    # On supprime l'action de suppression par defaut de la liste des covoitureurs
    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    # On ajoute le traitement de la fusion de nom
    def merge_name(self, request, queryset_tags):

        datasets = Dataset.objects.filter(keywords__in=queryset_tags).distinct()
        if 'apply' in request.POST:
            form = NewKeywordForm(request.POST)
            if form.is_valid():
                error = False

                name = form.cleaned_data.get('new_name')
                tag, created = Tag.objects.get_or_create(name=name)
                # WIP

                for dataset in datasets:
                    dataset.keywords.add(tag)
                    ckan_id = str(dataset.ckan_id)
                    qs_dataset_keywords = dataset.keywords.all().exclude(id__in=queryset_tags)

                    tags = [
                        *[{'name': k.name} for k in qs_dataset_keywords],
                        *[{'name': tag.name}]]

                    logger.info('Update dataset %d with tags: %s' % (dataset.pk, tags))
                    try:
                        CkanHandler.publish_dataset(id=ckan_id, tags=tags)
                    except CkanBaseError as e:
                        logger.exception(e)
                        error = True
                        dataset.keywords.remove(tag)
                        break
                    else:
                        continue
                if error:
                    messages.error(request, (
                        "Une erreur est survenue. "
                        "Veuillez contacter l'administrateur de la plateforme."
                        ))
                else:
                    queryset_tags.exclude(pk=tag.pk).delete()
                    messages.info(request, (
                        "La mise à jour est effectuée avec succès."
                        ))
                return HttpResponseRedirect(request.get_full_path())

        else:  # request.GET
            form = NewKeywordForm()
        # then
        template_html = 'admin/idgo_admin/taggit_merge_name.html'
        context = {'form': form, 'tags': queryset_tags, 'datasets': datasets}
        return render(request, template_html, context=context)

    merge_name.short_description = "Renommer/fusionner le ou les mots-clés sélectionnés"


admin.site.register(Keywords, KeywordsAdmin)
