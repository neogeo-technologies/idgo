from .models import Category
from .models import Commune
from .models import Dataset
from .models import ResourceFormats
from .models import License
from .models import Resource
from .models import Jurisdiction
from .models import Mail
from .models import Organisation
from .models import OrganisationType
from .models import Profile

from django.contrib import admin
from django.contrib.gis import admin as geo_admin

from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.models import User

geo_admin.GeoModelAdmin.default_lon = 160595
geo_admin.GeoModelAdmin.default_lat = 5404331
geo_admin.GeoModelAdmin.default_zoom = 14

admin.site.register(Category)
admin.site.register(Commune)
admin.site.register(Jurisdiction)
admin.site.register(License)
admin.site.register(OrganisationType)
admin.site.register(Profile)
admin.site.register(ResourceFormats)
admin.site.unregister(User)


class ResourceInline(admin.StackedInline):
    model = Resource
    max_num = 5
    can_delete = True
    readonly_fields = ('bbox',)


class DatasetAdmin(admin.ModelAdmin):
    inlines = [ResourceInline]


admin.site.register(Dataset, DatasetAdmin)


class UserProfileInline(admin.StackedInline):
    model = Profile
    max_num = 1
    can_delete = False
    readonly_fields = ('phone', 'organisation')


class UserAdmin(AuthUserAdmin):
    inlines = [UserProfileInline]


admin.site.register(User, UserAdmin)


class OrganisationAdmin(geo_admin.OSMGeoAdmin):
    list_display = ('name', 'organisation_type')
    list_filter = ('organisation_type',)
    # prepopulated_fields = {"ckan_slug": ("name",)}
    readonly_fields = ('ckan_slug', )


admin.site.register(Organisation, OrganisationAdmin)


class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'url')
    search_fields = ('name', 'short_name')
    list_filter = ('host',)


class MailAdmin(admin.ModelAdmin):
    model = Mail

    # Vue dev:
    # list_display = ('template_name', 'subject', )
    # fieldsets = (
    #     ('Personnalisation des messages automatiques',
    #      {'fields': ('template_name', 'subject', 'message', 'from_email')}),)
    # Fin vue dev

    # Vue client:
    list_display = ('subject', )
    fieldsets = (
        ('Personnalisation des messages automatiques',
         {'fields': ('subject', 'message', )}),)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False
    # Fin Vue client


admin.site.register(Mail, MailAdmin)
