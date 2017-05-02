from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.gis import admin as geo_admin

from .models import Organisation, Profile, OrganisationType, Application


geo_admin.GeoModelAdmin.default_lon = 160595
geo_admin.GeoModelAdmin.default_lat = 5404331
geo_admin.GeoModelAdmin.default_zoom = 14


admin.site.register(OrganisationType)
admin.site.unregister(User)


class UserProfileInline(admin.StackedInline):
   model = Profile
   max_num = 1
   can_delete = False
   readonly_fields = ('activation_key', 'key_expires')


class UserAdmin(AuthUserAdmin):
   inlines = [UserProfileInline]


admin.site.register(User, UserAdmin)


class OrganisationAdmin(geo_admin.OSMGeoAdmin):
    list_display = ('name', 'organisation_type', 'parent')
    list_filter = ('organisation_type',)
    #prepopulated_fields = {"ckan_slug": ("name",)}
    readonly_fields = ('ckan_slug','sync_in_ldap', 'sync_in_ckan')


admin.site.register(Organisation, OrganisationAdmin)


class ApplicationAdmin(admin.ModelAdmin):
    list_display=('name', 'url', 'sync_in_ldap')
    search_fields = ('name','short_name')
    list_filter = ('sync_in_ldap', 'host')


admin.site.register(Application, ApplicationAdmin)