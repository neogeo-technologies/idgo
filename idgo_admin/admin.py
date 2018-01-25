from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.contrib.gis import admin as geo_admin
# from django.contrib import messages
# from django.utils.text import slugify
# from idgo_admin.ckan_module import CkanManagerHandler
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
from django.contrib.auth.forms import UserCreationForm
from django.core.mail import send_mail
from django.urls import reverse
from idgo_admin.ckan_module import CkanHandler as ckan
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.auth.views import redirect_to_login

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


# class EmailRequiredMixin(object):
#     def __init__(self, *args, **kwargs):
#         super(EmailRequiredMixin, self).__init__(*args, **kwargs)
#         # make user email field required
#         self.fields['email'].required = True


class MyUserCreationForm(UserCreationForm):

    class Meta():
        model = User
        fields = ('first_name', 'last_name', 'email', 'username')

    def __init__(self, *args, **kwargs):
        self._request = self.request
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

    def password_generator(self, N=8):
        import string
        import random
        return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(N))

    def send_credentials_to_user(self, cleaned_data, pass_generated, request=None):

        from_email = settings.DEFAULT_FROM_EMAIL
        subject = "Un nouveau compte vous a été crée par le service d'administration de la plateforme Datasud "
        data = {
            'username': cleaned_data.get('username'),
            'first_name': cleaned_data.get('first_name'),
            'last_name': cleaned_data.get('last_name').upper(),
            'password': pass_generated}

        data['url'] = request.build_absolute_uri(reverse('idgo_admin:account_manager', kwargs={'process': 'update'}))

        message = """\
            <html>
              <head></head>
              <body>
                    Bonjour, {last_name}, {first_name}<br>
                    <p>Un compte vous a été créé sur la plateforme Datasud. </p>
                    <p>Après votre premiere connexion, veuillez <b>réinitializer</b> votre mot de passe. </p>
                    <br>
                    <p>Identifiant de connexion: <b>{username}</b> </p>
                    <p>Mot de passe: {password}</p>
                    <p>Url de connexion: {url}</p>
                    <br>
                    <p>Ce message est envoyé automatiquement...</p>
             </body>
            </html>
            """.format(**data)
        send_mail(subject=subject, message=message,
                  from_email=from_email, recipient_list=[self.cleaned_data['email']])

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists() or ckan.is_user_exists(username):
            raise forms.ValidationError("Ce nom d'utilisateur est reservé")
        return username

    def clean_password2(self):
        return "overwrited password"

    def save(self, commit=True, *args, **kwargs):
        user = super(UserCreationForm, self).save(commit=False)
        pass_generated = self.password_generator()
        self.send_credentials_to_user(self.cleaned_data, pass_generated, request=self._request)
        try:
            ckan.add_user(user, pass_generated)
        except Exception as e:
            ValidationError("L'ajout de l'utilisateur sur CKAN à echoué: {}".format(e))
        user.set_password(pass_generated)
        if commit:
            user.save()
        return user


class UserProfileInline(admin.StackedInline):
    model = Profile
    max_num = 1

    # def has_delete_permission(self, request, obj=None):
    #     return False

    # def has_add_permission(self, request, obj=None):
    #     return False


class UserAdmin(AuthUserAdmin):
    inlines = [UserProfileInline]
    add_form = MyUserCreationForm
    list_display = ('full_name', 'username', 'is_superuser', 'is_active')
    list_display_links = ('username', )
    ordering = ('last_name', 'first_name')
    prepopulated_fields = {'username': ('first_name', 'last_name',)}
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'username',
                       'email', 'password1', 'password2'),
            }),
        )

    # def has_delete_permission(self, request, obj=None):
    #     return False

    # def has_add_permission(self, request, obj=None):
    #     return False

    # def get_actions(self, request):
    #     actions = super(UserAdmin, self).get_actions(request)
    #     if 'delete_selected' in actions:
    #         del actions['delete_selected']
    #     return actions

    # Necessaire pour ajouter la 'request' dans MyUserCreationForm.__init__
    def get_form(self, request, obj=None, **kwargs):
        add_form = super(UserAdmin, self).get_form(request, obj=obj, **kwargs)
        add_form.request = request
        return add_form

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
    # actions = ['sync_ckan']
    readonly_fields = ('ckan_slug',)
    ordering = ('name',)

    # def sync_ckan(self, request, queryset):
    #     ckan = CkanManagerHandler()
    #     neworgs = []
    #     for category in queryset:
    #
    #         current_slug = category.ckan_slug
    #         correct_slug = slugify(category.name)
    #         if not category.ckan_slug or (current_slug != correct_slug):
    #             category.save()
    #             neworgs.append(category.name)
    #             continue
    #
    #         if not ckan.is_group_exists(category.ckan_slug):
    #             ckan.add_group(category)
    #             neworgs.append(category.name)
    #
    #     if len(neworgs) == 0:
    #         messages.error(request, "Aucune catégorie n'a dû être synchronisée")
    #     else:
    #         msg = ("Les catégories suivantes ont été synchronisées avec "
    #                "les données CKAN: {0}".format(set(neworgs)))
    #         messages.success(request, msg)
    # sync_ckan.short_description = 'Synchronisation des catégories séléctionnées'

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super(CategoryAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


admin.site.register(Category, CategoryAdmin)
