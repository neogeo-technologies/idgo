from django.contrib import admin
from idgo_admin.models import Dataset
from idgo_admin.models import Resource
from idgo_admin.models import ResourceFormats


class ResourceFormatsAdmin(admin.ModelAdmin):
    ordering = ("extension", )


admin.site.register(ResourceFormats, ResourceFormatsAdmin)


class ResourceInline(admin.StackedInline):
    model = Resource
    max_num = 5
    can_delete = True

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(set(
            [field.name for field in self.opts.local_fields] +
            [field.name for field in self.opts.local_many_to_many]
            ))
        return readonly_fields


class DatasetAdmin(admin.ModelAdmin):

    # list_display = ('name', 'full_name', 'organisation', 'nb_resources')
    inlines = [ResourceInline]
    ordering = ('name', )

    # def nb_resources(self, obj):
    #     return Resource.objects.filter(dataset=obj).count()
    # nb_resources.short_description = "Nombre de ressources"

    # def full_name(self, obj):
    #     return obj.editor.get_full_name()
    # full_name.short_description = "Nom de l'éditeur"

    # def has_delete_permission(self, request, obj=None):
    #     return False
    #
    # def has_add_permission(self, request, obj=None):
    #     return False
    #
    # def get_actions(self, request):
    #     actions = super(DatasetAdmin, self).get_actions(request)
    #     if 'delete_selected' in actions:
    #         del actions['delete_selected']
    #     return actions

    # def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
    #     extra_context = extra_context or {}
    #     extra_context['show_save_and_continue'] = False
    #     extra_context['show_save'] = False
    #     return super(DatasetAdmin, self).changeform_view(request, object_id, extra_context=extra_context)

    def get_readonly_fields(self, request, obj=None):
        # readonly_fields = list(set(
        #     [field.name for field in self.opts.local_fields] +
        #     [field.name for field in self.opts.local_many_to_many]
        #     ))
        readonly_fields = (
            'ckan_id', 'ckan_slug', 'geonet_id')
        return readonly_fields


admin.site.register(Dataset, DatasetAdmin)
