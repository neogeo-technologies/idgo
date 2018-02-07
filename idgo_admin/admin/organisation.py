from django.contrib import admin
from django.contrib.gis import admin as geo_admin
from idgo_admin.models import Organisation
from idgo_admin.models import OrganisationType


geo_admin.GeoModelAdmin.default_lon = 160595
geo_admin.GeoModelAdmin.default_lat = 5404331
geo_admin.GeoModelAdmin.default_zoom = 14


class OrganisationAdmin(geo_admin.OSMGeoAdmin):
    # actions = ['really_delete_selected']
    list_display = ('name', 'organisation_type')
    list_filter = ('organisation_type',)
    ordering = ('name',)

    # Permet d'empecher la modification du nom et du slug d'une organisation aprés sa création
    def get_readonly_fields(self, request, obj=None):
        return ['ckan_slug']
        # if obj:
        #     return ['name', 'ckan_slug']
        # else:
        #     return ['ckan_slug']

    # def has_delete_permission(self, request, obj=None):
    #     return False

    # def has_add_permission(self, request, obj=None):
    #     return False

    # def get_actions(self, request):
    #     actions = super(OrganisationAdmin, self).get_actions(request)
    #     if 'delete_selected' in actions:
    #         del actions['delete_selected']
    #     return actions
    #
    # def really_delete_selected(self, request, queryset):
    #     for instance in queryset:
    #         instance.delete()
    #     message = "La ou les organisations sélectionnées ont été supprimées correctement."
    #     self.message_user(request, message)
    #
    # really_delete_selected.short_description = "Supprimer les organisations sélectionnées"

admin.site.register(Organisation, OrganisationAdmin)


class OrganisationTypeAdmin(admin.ModelAdmin):
    ordering = ('name', )
    search_fields = ('name', 'code')


admin.site.register(OrganisationType, OrganisationTypeAdmin)
