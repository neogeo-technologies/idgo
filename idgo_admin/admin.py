from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.contrib.gis import admin as geo_admin
from django.contrib import messages
from django.utils.text import slugify
from idgo_admin.ckan_module import CkanManagerHandler
from idgo_admin.models import Category
from idgo_admin.models import Dataset
from idgo_admin.models import Financier
from idgo_admin.models import Jurisdiction
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import License
from idgo_admin.models import Mail
from idgo_admin.models import Organisation
from idgo_admin.models import OrganisationType
from idgo_admin.models import Profile
from idgo_admin.models import Resource
from idgo_admin.models import ResourceFormats
from taggit.admin import Tag


geo_admin.GeoModelAdmin.default_lon = 160595
geo_admin.GeoModelAdmin.default_lat = 5404331
geo_admin.GeoModelAdmin.default_zoom = 14

admin.site.unregister(Group)
admin.site.unregister(User)
admin.site.unregister(Tag)


class JurisdictionAdmin(admin.ModelAdmin):
    ordering = ("name", )
    search_fields = ('name', 'commune')


admin.site.register(Jurisdiction, JurisdictionAdmin)


class FinancierAdmin(admin.ModelAdmin):
    ordering = ("name", )
    search_fields = ('name', 'code')


admin.site.register(Financier, FinancierAdmin)


class OrganisationTypeAdmin(admin.ModelAdmin):
    ordering = ("name", )
    search_fields = ('name', 'code')


admin.site.register(OrganisationType, OrganisationTypeAdmin)


class LicensenAdmin(admin.ModelAdmin):
    ordering = ("title", )


admin.site.register(License, LicensenAdmin)


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
    list_display = ('name', 'full_name', 'organisation', 'nb_resources')
    inlines = [ResourceInline]
    ordering = ('name', )

    def nb_resources(self, obj):
        return Resource.objects.filter(dataset=obj).count()
    nb_resources.short_description = "Nombre de ressources"

    def full_name(self, obj):
        return obj.editor.get_full_name()
    full_name.short_description = "Nom de l'éditeur"

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super(DatasetAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_save_and_continue'] = False
        extra_context['show_save'] = False
        return super(DatasetAdmin, self).changeform_view(request, object_id, extra_context=extra_context)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(set(
            [field.name for field in self.opts.local_fields] +
            [field.name for field in self.opts.local_many_to_many]
            ))
        return readonly_fields


admin.site.register(Dataset, DatasetAdmin)


class CustomLiaisonsReferentsModelForm(forms.ModelForm):

    model = LiaisonsReferents
    fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(CustomLiaisonsReferentsModelForm, self).__init__(*args, **kwargs)
        self.fields['organisation'].queryset = Organisation.objects.filter(is_active=True)


class LiaisonReferentsInline(admin.TabularInline):
    model = LiaisonsReferents
    form = CustomLiaisonsReferentsModelForm
    extra = 0
    verbose_name_plural = "Organisations pour lesquelles l'utilisateur est référent"
    verbose_name = "Organisation"


class ProfileAdmin(admin.ModelAdmin):
    inlines = (LiaisonReferentsInline,)
    models = Profile
    list_display = ('full_name', 'username', 'is_admin')
    search_fields = ('user__username', 'user__last_name')
    ordering = ('user__last_name', 'user__first_name')

    def username(self, obj):
        return str(obj.user.username)

    def full_name(self, obj):
        return " ".join((obj.user.last_name.upper(), obj.user.first_name.capitalize()))

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super(ProfileAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    username.short_description = "Nom d'utilisateur"
    full_name.short_description = "Nom et prénom"


admin.site.register(Profile, ProfileAdmin)


class UserProfileInline(admin.StackedInline):
    model = Profile
    max_num = 1

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


class UserAdmin(AuthUserAdmin):
    inlines = [UserProfileInline]
    list_display = ('full_name', 'username', 'is_superuser', 'is_active')
    list_display_links = ('username', )
    ordering = ('last_name', 'first_name')

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super(UserAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def full_name(self, obj):
        return " ".join((obj.last_name.upper(), obj.first_name.capitalize()))
    full_name.short_description = "Nom et prénom"


admin.site.register(User, UserAdmin)


class OrganisationAdmin(geo_admin.OSMGeoAdmin):
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

    def has_delete_permission(self, request, obj=None):
        return False

    # def has_add_permission(self, request, obj=None):
    #     return False

    def get_actions(self, request):
        actions = super(OrganisationAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


admin.site.register(Organisation, OrganisationAdmin)


# class ApplicationAdmin(admin.ModelAdmin):
#     list_display = ('name', 'url')
#     search_fields = ('name', 'short_name')
#     list_filter = ('host',)


class MailAdmin(admin.ModelAdmin):
    model = Mail
    ordering = ('subject',)
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

    def get_actions(self, request):
        actions = super(MailAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
    # Fin Vue client


admin.site.register(Mail, MailAdmin)


class CategoryAdmin(admin.ModelAdmin):
    model = Category
    actions = ['sync_ckan']
    readonly_fields = ('ckan_slug',)
    ordering = ('name',)

    def sync_ckan(self, request, queryset):
        ckan = CkanManagerHandler()
        neworgs = []
        for category in queryset:

            current_slug = category.ckan_slug
            correct_slug = slugify(category.name)
            if not category.ckan_slug or (current_slug != correct_slug):
                category.save()
                neworgs.append(category.name)
                continue

            if not ckan.is_group_exists(category.ckan_slug):
                ckan.add_group(category)
                neworgs.append(category.name)

        if len(neworgs) == 0:
            messages.error(request, "Aucune catégorie n'a dû être synchronisée")
        else:
            msg = ("Les catégories suivantes ont été synchronisées avec "
                   "les données CKAN: {0}".format(set(neworgs)))
            messages.success(request, msg)
    sync_ckan.short_description = 'Synchronisation des catégories séléctionnées'

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super(CategoryAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


admin.site.register(Category, CategoryAdmin)
