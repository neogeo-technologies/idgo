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

from django import forms
from django.conf.urls import url
from django.contrib import admin
from django.contrib import messages
from django.core.management import call_command
from django.shortcuts import redirect

from idgo_admin.models import Category


logger = logging.getLogger('glob')


class CategoryAdminForm(forms.ModelForm):

    class Meta(object):
        model = Category
        fields = '__all__'
        widgets = {
            'alternate_titles': forms.Textarea(),
        }


class CategoryAdmin(admin.ModelAdmin):
    form = CategoryAdminForm
    model = Category
    list_display = ('name', 'iso_topic', 'alternate_titles', )
    readonly_fields = ('slug', )
    ordering = ('name', )
    change_list_template = 'admin/idgo_admin/category_change_list.html'

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            url('sync-ckan-categories/', self.sync_ckan_categories_view, name='sync_ckan_categories'),
        ]
        return my_urls + urls

    def sync_ckan_categories_view(self, request):
        try:
            call_command('sync_ckan_categories')
        except Exception:
            logger.exception('CKAN Categories sync failed')
            messages.error(request, "Synchronisation échouée.")
        else:
            messages.success(request, "Synchronisation réussie.")

        return redirect('admin:idgo_admin_category_changelist')


admin.site.register(Category, CategoryAdmin)
