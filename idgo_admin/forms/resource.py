from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django import forms
from django.utils import timezone
from idgo_admin.ckan_module import CkanHandler as ckan
from idgo_admin.ckan_module import CkanUserHandler as ckan_me
from idgo_admin.exceptions import SizeLimitExceededError
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.models import Resource
from idgo_admin.models import ResourceFormats
from idgo_admin.utils import download
from idgo_admin.utils import readable_file_size
import json
from pathlib import Path

from django.db.utils import ProgrammingError
from django.contrib.auth.models import User
from django.db.models.query import QuerySet

_today = timezone.now().date()

try:
    DOWNLOAD_SIZE_LIMIT = settings.DOWNLOAD_SIZE_LIMIT
except AttributeError:
    DOWNLOAD_SIZE_LIMIT = 104857600  # 100Mio


def get_all_users_for_organizations(list_id):
    return [
        profile.user.username
        for profile in Profile.objects.filter(
            organisation__in=list_id, organisation__is_active=True)]


def file_size(value):
    size_limit = DOWNLOAD_SIZE_LIMIT
    if value.size > size_limit:
        message = \
            'Le fichier {0} ({1}) dépasse la limite de taille autorisée {2}.'.format(
                value.name, readable_file_size(value.size), readable_file_size(size_limit))
        raise ValidationError(message)


class ResourceForm(forms.ModelForm):

    class CustomClearableFileInput(forms.ClearableFileInput):
        template_name = 'idgo_admin/widgets/file_drop_zone.html'

    up_file = forms.FileField(
        label='Téléversement',
        required=False,
        validators=[file_size],
        widget=CustomClearableFileInput(
            attrs={'max_size_info': DOWNLOAD_SIZE_LIMIT}))

    # dl_url

    # referenced_url

    name = forms.CharField(
        label='Titre*',
        widget=forms.TextInput(
            attrs={'placeholder': 'Titre'}))

    description = forms.CharField(
        label='Description',
        required=False,
        widget=forms.Textarea(
            attrs={'placeholder': 'Vous pouvez utiliser le langage Markdown ici'}))

    # lang

    # data_format = forms.CharField(
    #     label='Format',
    #     widget=forms.TextInput(
    #         attrs={'placeholder': 'CSV, XML, JSON, XLS... '}))

    format_type = forms.ModelChoiceField(
        label='Format*',
        queryset=ResourceFormats.objects.all(),
        required=True)

    # restricted_level

    # def active_users():
    #     l = []
    #     active_profiles = Profile.objects.all()
    #     for ap in active_profiles:
    #         l.append(ap.phone)
    #     print(l)
    #     return User.objects.all()

    #
    # try:
    #     queryset = active_users()
    # except ProgrammingError as err:
    #     print(str(err))
    #     queryset = QuerySet().none()

    profiles_allowed = forms.ModelMultipleChoiceField(
        label='Utilisateurs autorisés',
        queryset=Profile.objects.filter(is_active=True),
        required=False,
        to_field_name="pk")

    organisations_allowed = forms.ModelMultipleChoiceField(
        label='Organisations autorisées',
        queryset=Organisation.objects.filter(is_active=True),
        required=False,
        to_field_name="pk")

    class Meta(object):
        model = Resource
        fields = ('up_file',
                  'dl_url',
                  'referenced_url',
                  'name',
                  'description',
                  'lang',
                  'format_type',
                  'restricted_level',
                  'profiles_allowed',
                  'organisations_allowed')

    def __init__(self, *args, **kwargs):

        self.include_args = kwargs.pop('include', {})
        super().__init__(*args, **kwargs)

        ckan_orga = ckan.get_all_organizations()

        self.fields['organisations_allowed'].queryset = \
            Organisation.objects.filter(is_active=True, ckan_slug__in=ckan_orga)

    def handle_me(
            self, request, dataset, id=None, uploaded_file=None):

        user = request.user
        data = self.cleaned_data
        restricted_level = data['restricted_level']
        profiles_allowed = data['profiles_allowed']
        organizations_allowed = data['organisations_allowed']

        params = {'name': data['name'],
                  'description': data['description'],
                  'dl_url': data['dl_url'],
                  'referenced_url': data['referenced_url'],
                  'lang': data['lang'],
                  'format_type': data['format_type'],
                  'restricted_level': restricted_level,
                  'up_file': data['up_file'],
                  'dataset': dataset}

        if id:  # Mise à jour de la ressource
            created = False
            resource = Resource.objects.get(pk=id)
            for key, value in params.items():
                setattr(resource, key, value)
        else:  # Création d'une nouvelle ressource
            created = True
            resource = Resource.objects.create(**params)

        ckan_user = ckan_me(ckan.get_user(user.username)['apikey'])

        ckan_params = {
            'name': resource.name,
            'description': resource.description,
            'format': resource.format_type.extension,
            'view_type': resource.format_type.ckan_view,
            'id': str(resource.ckan_id),
            'lang': resource.lang,
            'url': ''}

        if restricted_level == '0':  # Public
            resource.profiles_allowed = profiles_allowed
            ckan_params['restricted'] = json.dumps({'level': 'public'})

        if restricted_level == '1':  # Registered users
            resource.profiles_allowed = profiles_allowed
            ckan_params['restricted'] = json.dumps({'level': 'registered'})

        if restricted_level == '2':  # Only allowed users
            resource.profiles_allowed = profiles_allowed
            ckan_params['restricted'] = json.dumps({
                'allowed_users': ','.join([p.user.username for p in profiles_allowed]),
                'level': 'only_allowed_users'})

        if restricted_level == '3':  # This organization
            resource.organisations_allowed = [dataset.organisation]
            ckan_params['restricted'] = json.dumps({
                'allowed_users': ','.join(
                    get_all_users_for_organizations([dataset.organisation])),
                'level': 'only_allowed_users'})

        if restricted_level == '4':  # Any organization
            resource.organisations_allowed = organizations_allowed
            ckan_params['restricted'] = json.dumps({
                'allowed_users': ','.join(
                    get_all_users_for_organizations(organizations_allowed)),
                'level': 'only_allowed_users'})

        if resource.referenced_url:
            ckan_params['url'] = resource.referenced_url
            ckan_params['resource_type'] = \
                '{0}.{1}'.format(resource.name, resource.format_type.ckan_view)

        if resource.dl_url:
            try:
                filename, content_type = download(
                    resource.dl_url, settings.MEDIA_ROOT,
                    max_size=DOWNLOAD_SIZE_LIMIT)
            except SizeLimitExceededError as e:
                l = len(str(e.max_size))
                if l > 6:
                    m = '{0} mo'.format(Decimal(int(e.max_size) / 1024 / 1024))
                elif l > 3:
                    m = '{0} ko'.format(Decimal(int(e.max_size) / 1024))
                else:
                    m = '{0} octets'.format(int(e.max_size))
                raise ValidationError(
                    "La taille du fichier dépasse la limite autorisée : {0}.".format(m), code='dl_url')

            downloaded_file = File(open(filename, 'rb'))
            ckan_params['upload'] = downloaded_file
            ckan_params['size'] = downloaded_file.size
            ckan_params['mimetype'] = content_type
            ckan_params['resource_type'] = Path(filename).name

        if uploaded_file:
            ckan_params['upload'] = resource.up_file.file
            ckan_params['size'] = uploaded_file.size
            ckan_params['mimetype'] = uploaded_file.content_type
            ckan_params['resource_type'] = uploaded_file.name

        try:
            ckan_user.publish_resource(str(dataset.ckan_id), **ckan_params)
        except Exception as e:
            if created:
                resource.delete()
            # else:
            #     resource.sync_in_ckan = False
            raise e
        else:
            # resource.sync_in_ckan = True
            resource.last_update = _today
            resource.save()
        finally:
            ckan_user.close()

        return resource

    def clean(self):

        up_file = self.cleaned_data.get('up_file', None)
        dl_url = self.cleaned_data.get('dl_url', None)
        referenced_url = self.cleaned_data.get('referenced_url', None)
        res_l = [up_file, dl_url, referenced_url]
        if all(v is None for v in res_l):
            self.add_error('up_file', "Veuillez indiquer un type de ressource.")
            self.add_error('dl_url', "Veuillez indiquer un type de ressource.")
            self.add_error('referenced_url', "Veuillez indiquer un type de ressource.")
            raise ValidationError('ResourceType')
        if sum(v is not None for v in res_l) > 1:
            self.add_error('up_file', "Un seul type de ressource n'est autorisé.")
            self.add_error('dl_url', "Un seul type de ressource n'est autorisé.")
            self.add_error('referenced_url', "Un seul type de ressource n'est autorisé.")
            raise ValidationError('ResourceType')
