from django.contrib import admin

from idgo_admin.models.data_type import DataType


class DataTypeAdmin(admin.ModelAdmin):
    list_display = ['slug', 'name', 'description']
    ordering = ['slug']
    can_add_related = False
    can_delete_related = False
    search_fields = ['name', ]
    actions = None

    # Si on veut ajouter des actions ultérieurs tout en empechant
    # l'action de suppression depuis la liste
    # def get_actions(self, request):
    #     actions = super().get_actions(request)
    #     if 'delete_selected' in actions:
    #         del actions['delete_selected']
    #     return actions


admin.site.register(DataType, DataTypeAdmin)
