from django.contrib import admin
from idgo_admin.models import Dataset
from idgo_admin.models import Resource
from idgo_admin.models import ResourceFormats


class ResourceFormatsAdmin(admin.ModelAdmin):
    ordering = ("extension", )

    def __init__(self, *args, **kwargs):
        super(ResourceFormatsAdmin, self).__init__(*args, **kwargs)

    def has_add_permission(self, request):
        return True

    class Meta:
        model = Resource


admin.site.register(ResourceFormats, ResourceFormatsAdmin)


class ResourceInline(admin.StackedInline):
    model = Resource
    extra = 0
    can_delete = True

    fieldsets = (
        ('Synchronisation distante', {
            'classes': ('collapse',),
            'fields': ('synchronisation', 'sync_frequency', 'custom_frequency', ),
            }),
        (None, {
            'classes': ('wide', ),
            'fields': (
                ('name', 'description'),
                ('referenced_url', 'dl_url', 'up_file'),
                'lang',
                'format_type', 'restricted_level', 'profiles_allowed',
                'organisations_allowed', 'bbox', 'geo_restriction',
                'created_on', 'last_update',)
            }),
        )


class DatasetAdmin(admin.ModelAdmin):

    list_display = ('name', 'nb_resources', )
    inlines = (ResourceInline, )
    ordering = ('name', )
    can_add_related = True
    can_delete_related = True
    readonly_fields = ('ckan_id', 'ckan_slug', 'geonet_id')

    def nb_resources(self, obj):
        return Resource.objects.filter(dataset=obj).count()
    nb_resources.short_description = "Nombre de ressources"


admin.site.register(Dataset, DatasetAdmin)
