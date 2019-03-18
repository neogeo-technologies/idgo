from django.contrib import admin

from ihm.models import IHMSettings


class IHMSettingsAdmin(admin.ModelAdmin):

    list_display = ('name', 'contents', 'target')

    def get_readonly_fields(self, request, obj=None):
        return obj and ["name", ] or []

    def get_actions(self, request):
        actions = super().get_actions(request)

        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


admin.site.register(IHMSettings, IHMSettingsAdmin)
