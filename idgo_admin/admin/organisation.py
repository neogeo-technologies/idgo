from django.contrib import admin
from django.contrib.gis import admin as geo_admin
from idgo_admin.models import Organisation
from idgo_admin.models import OrganisationType


geo_admin.GeoModelAdmin.default_lon = 160595
geo_admin.GeoModelAdmin.default_lat = 5404331
geo_admin.GeoModelAdmin.default_zoom = 14


class OrganisationAdmin(geo_admin.OSMGeoAdmin):

    list_display = ('name', 'organisation_type')
    list_filter = ('organisation_type',)
    ordering = ('name',)
    readonly_fields = ('ckan_slug', )

    # Champ name modifiable lors du /add
    # Champs name et ckan_slug NON modifiables lors du /change
    # def get_readonly_fields(self, request, obj=None):
    #     if obj:
    #         return ['name', 'ckan_slug']
    #     else:
    #         return ['ckan_slug']


admin.site.register(Organisation, OrganisationAdmin)


class OrganisationTypeAdmin(admin.ModelAdmin):
    ordering = ('name', )
    search_fields = ('name', 'code')


admin.site.register(OrganisationType, OrganisationTypeAdmin)
