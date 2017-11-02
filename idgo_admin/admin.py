from .models import Category
from .models import Dataset
from .models import ResourceFormats
from .models import License
from .models import Resource
from .models import Jurisdiction
from .models import Mail
from .models import Organisation
from .models import OrganisationType
from .models import Profile
from taggit.admin import Tag

from django.contrib import admin
from django.contrib.gis import admin as geo_admin

from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.models import Group
from django.contrib.auth.models import User

geo_admin.GeoModelAdmin.default_lon = 160595
geo_admin.GeoModelAdmin.default_lat = 5404331
geo_admin.GeoModelAdmin.default_zoom = 14

admin.site.register(Category)
admin.site.register(Jurisdiction)
admin.site.register(License)
admin.site.register(OrganisationType)
admin.site.register(Profile)
admin.site.register(ResourceFormats)
admin.site.unregister(Group)
admin.site.unregister(User)
admin.site.unregister(Tag)


class ResourceInline(admin.StackedInline):
    model = Resource
    max_num = 5
    can_delete = True
    readonly_fields = ('bbox',)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


class DatasetAdmin(admin.ModelAdmin):
    list_display = ('name', 'full_name', 'organisation', 'nb_resources')
    inlines = [ResourceInline]

    def nb_resources(self, obj):
        return Resource.objects.filter(dataset=obj).count()
    nb_resources.short_description = "Nombre de ressources"

    def full_name(self, obj):
        return obj.editor.get_full_name()
        # return obj.author.user.get_full_name()
    full_name.short_description = "Nom de l'éditeur"

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


admin.site.register(Dataset, DatasetAdmin)


class UserProfileInline(admin.StackedInline):
    model = Profile
    max_num = 1

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


class UserAdmin(AuthUserAdmin):
    inlines = [UserProfileInline]

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


admin.site.register(User, UserAdmin)


class OrganisationAdmin(geo_admin.OSMGeoAdmin):
    list_display = ('name', 'organisation_type')
    list_filter = ('organisation_type',)
    readonly_fields = ('ckan_slug', )

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


admin.site.register(Organisation, OrganisationAdmin)


# class ApplicationAdmin(admin.ModelAdmin):
#     list_display = ('name', 'url')
#     search_fields = ('name', 'short_name')
#     list_filter = ('host',)


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
