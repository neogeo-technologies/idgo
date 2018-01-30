from django import forms
from django.contrib import admin
from django.conf.urls import url
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.contrib.gis import admin as geo_admin
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
# from django.contrib import messages
# from django.utils.text import slugify
# from idgo_admin.ckan_module import CkanManagerHandler
from idgo_admin.ckan_module import CkanHandler as ckan

from idgo_admin.models import LiaisonsReferents

from idgo_admin.models import Mail
from idgo_admin.models import Organisation
from idgo_admin.models import Dataset

from idgo_admin.models import Profile


from taggit.admin import Tag

from django.utils.html import format_html
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from idgo_admin.exceptions import ErrorOnDeleteAccount
from idgo_admin.forms.account import DeleteAdminForm

geo_admin.GeoModelAdmin.default_lon = 160595
geo_admin.GeoModelAdmin.default_lat = 5404331
geo_admin.GeoModelAdmin.default_zoom = 14

admin.site.unregister(Group)
admin.site.unregister(User)
admin.site.unregister(Tag)


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
        self.fields['password1'].required = False
        self.fields['password2'].required = False

    def clean(self):
        self.cleaned_data['password1'] = "new_password_will_be_generated"
        self.cleaned_data['password2'] = "new_password_will_be_generated"
        return self.cleaned_data

    def password_generator(self, N=8):
        import string
        import random
        return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(N))

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists() or ckan.is_user_exists(username):
            raise forms.ValidationError("Ce nom d'utilisateur est reservé")
        return username

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1", "new_password_will_be_generated")
        password2 = self.cleaned_data.get("password2", "new_password_will_be_generated")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                self.error_messages['password_mismatch'],
                code='password_mismatch',
                )

    def save(self, commit=True, *args, **kwargs):
        user = super(UserCreationForm, self).save(commit=False)
        pass_generated = self.password_generator()
        Mail.send_credentials_user_creation_admin(self._request, self.cleaned_data, pass_generated)
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
    list_display = ('full_name', 'username', 'is_superuser', 'is_active', 'delete_account_action')
    list_display_links = ('username', )
    ordering = ('last_name', 'first_name')
    prepopulated_fields = {'username': ('first_name', 'last_name',)}
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'username',
                       'email'),
            }),
        )

    def has_delete_permission(self, request, obj=None):
        return False
    # def has_add_permission(self, request, obj=None):
    #     return False

    def get_actions(self, request):
        actions = super(UserAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    # Necessaire pour ajouter la 'request' dans MyUserCreationForm.__init__
    def get_form(self, request, obj=None, **kwargs):
        add_form = super(UserAdmin, self).get_form(request, obj=obj, **kwargs)
        add_form.request = request
        return add_form

    def full_name(self, obj):
        return " ".join((obj.last_name.upper(), obj.first_name.capitalize()))
    full_name.short_description = "Nom et prénom"

    def process_action(self, request, user_id, action_form, action_title):

        user = self.get_object(request, user_id)
        related_datasets = Dataset.objects.filter(editor=user)

        if request.method != 'POST':
            form = action_form(
                include={
                    'user_id': user_id,
                    'related_datasets': related_datasets
                    }
                )

        else:
            form = action_form(
                request.POST,
                include={
                    'user_id': user_id,
                    'related_datasets': related_datasets
                    }
                )
            if form.is_valid():
                try:
                    form.delete_controller(user, form.cleaned_data.get("new_user"), related_datasets)
                except ErrorOnDeleteAccount:
                    raise

                else:
                    self.message_user(
                        request,
                        'Le compte utilisateur a bien été supprimé'
                        )
                    url = reverse(
                        'admin:auth_user_changelist',
                        current_app=self.admin_site.name
                        )
                    return HttpResponseRedirect(url)

        context = self.admin_site.each_context(request)
        context['opts'] = self.model._meta
        context['form'] = form
        context['user'] = user
        context['title'] = action_title
        context['related_datasets'] = related_datasets

        return TemplateResponse(
            request,
            'admin/idgo_admin/user_action.html',
            context)

    def process_deleting(self, request, user_id, *args, **kwargs):
        return self.process_action(
            request=request,
            user_id=user_id,
            action_form=DeleteAdminForm,
            action_title="Suppression d'un compte utilisateur")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            url(
                r'^(?P<user_id>.+)/delete-account/$',
                self.admin_site.admin_view(self.process_deleting),
                name='delete-account'
                )
            ]
        return custom_urls + urls

    def delete_account_action(self, obj):
        return format_html(
            '<a class="button" href="{}">Supprimer</a>&nbsp;',
            reverse('admin:delete-account', args=[obj.pk]))

    delete_account_action.short_description = 'Supprimer'
    delete_account_action.allow_tags = True


admin.site.register(User, UserAdmin)
