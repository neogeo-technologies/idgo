from ckanapi import errors as CkanError
from ckanapi import RemoteCKAN
from datetime import datetime
from django.conf import settings
from django.db import IntegrityError
from functools import wraps
from idgo_admin.exceptions import ConflictError
from idgo_admin.exceptions import FakeError
from idgo_admin.exceptions import GenericException
from idgo_admin.utils import Singleton
from urllib.parse import urljoin


CKAN_URL = settings.CKAN_URL
CKAN_API_KEY = settings.CKAN_API_KEY


class CkanSyncingError(GenericException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class CkanExceptionsHandler(object):

    def __init__(self, ignore=None):
        self.ignore = ignore or []

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                name = e.__class__.__qualname__
                message = e.__str__()
                if self.is_ignored(e):
                    return f(*args, **kwargs)
                print('[~ Ckan Error ~]', name, message)
                raise CkanSyncingError(name=name, message=message)
        return wrapper

    def is_ignored(self, exception):
        return type(exception) in self.ignore


class CkanUserHandler(object):

    def __init__(self, api_key):
        self.remote = RemoteCKAN(CKAN_URL, apikey=api_key)

    def close(self):
        self.remote.close()

    @CkanExceptionsHandler(ignore=[CkanError.NotFound])
    def get_package(self, id):
        try:
            return self.remote.action.package_show(
                id=id, include_tracking=True)
        except CkanError.NotFound:
            return False

    def is_package_exists(self, id):
        return self.get_package(id) and True or False

    def is_package_name_already_used(self, name):
        return self.get_package(name) and True or False

    @CkanExceptionsHandler()
    def push_resource(self, package, **kwargs):
        kwargs['package_id'] = package['id']
        kwargs['created'] = datetime.now().isoformat()

        for resource in package['resources']:
            if resource['id'] == kwargs['id']:
                kwargs['last_modified'] = kwargs['created']
                del kwargs['created']
                del kwargs['url']
                resource.update(kwargs)
                del resource['tracking_summary']
                return self.remote.action.resource_update(**resource)
        return self.remote.action.resource_create(**kwargs)

    @CkanExceptionsHandler()
    def push_resource_view(self, **kwargs):

        kwargs['title'] = kwargs['title'] if 'title' in kwargs else 'Aperçu'
        kwargs['description'] = kwargs['description'] \
            if 'description' in kwargs else 'Aperçu du jeu de données'

        views = self.remote.action.resource_view_list(id=kwargs['resource_id'])
        for view in views:
            if view['view_type'] == kwargs['view_type']:
                return self.remote.action.resource_view_update(id=view['id'], **kwargs)
        return self.remote.action.resource_view_create(**kwargs)

    def check_dataset_integrity(self, name):
        if self.is_package_name_already_used(name):
            raise ConflictError('Dataset already exists')

    @CkanExceptionsHandler()
    def publish_dataset(self, name, id=None, resources=None, **kwargs):
        kwargs['name'] = name
        if id and self.is_package_exists(id):
            package = self.remote.action.package_update(
                **{**self.get_package(id), **kwargs})
        else:
            package = self.remote.action.package_create(**kwargs)
        return package

    def publish_resource(self, dataset_id, **kwargs):
        resource = self.push_resource(self.get_package(dataset_id), **kwargs)
        resource_format = kwargs['format'].lower()
        supported_view = {'csv': 'recline_view',
                          'geojson': 'text_view',
                          'json': 'text_view',
                          'wms': 'geo_view',
                          'xls': 'recline_view',
                          'xlsc': 'recline_view',
                          'xml': 'text_view',
                          'pdf': 'pdf_view'}
        if resource_format in [k for k, v in supported_view.items()]:
            self.push_resource_view(
                resource_id=resource['id'],
                view_type=supported_view.get(resource_format))

    @CkanExceptionsHandler()
    def delete_resource(self, id):
        return self.remote.action.resource_delete(id=id)

    @CkanExceptionsHandler()
    def delete_dataset(self, id):
        return self.remote.action.package_delete(id=id)


class CkanManagerHandler(metaclass=Singleton):

    def __init__(self):
        self.remote = RemoteCKAN(CKAN_URL, apikey=CKAN_API_KEY)

    @CkanExceptionsHandler()
    def get_all_users(self):
        return [(user['name'], user['display_name'])
                for user in self.remote.action.user_list()
                if user['state'] == 'active']

    @CkanExceptionsHandler(ignore=[CkanError.NotFound])
    def get_user(self, username):
        try:
            return self.remote.action.user_show(id=username)
        except CkanError.NotFound:
            return None

    def is_user_exists(self, username):
        return self.get_user(username) and True or False

    @CkanExceptionsHandler()
    def add_user(self, user, password):
        params = {'email': user.email,
                  'fullname': user.get_full_name(),
                  'name': user.username,
                  'password': password,
                  'state': 'deleted'}
        user = self.remote.action.user_create(**params)

    @CkanExceptionsHandler()
    def del_user(self, username):
        # self.del_user_from_groups(username)
        self.del_user_from_organizations(username)
        self.remote.action.user_delete(id=username)

    @CkanExceptionsHandler()
    def update_user(self, user):
        if not self.is_user_exists:
            raise IntegrityError(
                'User {0} does not exists'.format(user.username))

        ckan_user = self.get_user(user.username)
        ckan_user.update({'email': user.email,
                          'fullname': user.get_full_name()})
        self.remote.action.user_update(**ckan_user)

    @CkanExceptionsHandler()
    def activate_user(self, username):
        ckan_user = self.get_user(username)
        ckan_user.update({'state': 'active'})
        self.remote.action.user_update(**ckan_user)

    @CkanExceptionsHandler()
    def get_all_organizations(self):
        return [organization
                for organization in self.remote.action.organization_list()]

    @CkanExceptionsHandler(ignore=[CkanError.NotFound])
    def get_organization(self, id):
        try:
            self.remote.action.organization_show(id=str(id))
        except CkanError.NotFound:
            return None

    def is_organization_exists(self, organization_id):
        return self.get_organization(str(organization_id)) and True or False

    @CkanExceptionsHandler(ignore=[FakeError])
    def add_organization(self, organization):
        params = {
            'id': str(organization.ckan_id),
            'name': organization.ckan_slug,
            'title': organization.name,
            'state': 'active'}
        try:
            params['image_url'] = \
                urljoin(settings.DOMAIN_NAME, organization.logo.url)
        except FakeError:
            pass
        self.remote.action.organization_create(**params)

    # @CkanExceptionsHandler()
    # def activate_organization(self, id):
    #     self.remote.action.organization_update(id=str(id), state='active')

    # @CkanExceptionsHandler()
    # def deactivate_organization(self, id):
    #     self.remote.action.organization_update(id=str(id), state='deleted')

    @CkanExceptionsHandler()
    def del_organization(self, id):
        self.remote.action.organization_purge(id=id)

    @CkanExceptionsHandler()
    def get_organizations_which_user_belongs(
            self, username, permission='manage_group'):

        # permission=read|create_dataset|manage_group
        res = self.remote.action.organization_list_for_user(
            id=username, permission=permission)
        return [d['name'] for d in res if d['is_organization']]

    @CkanExceptionsHandler()
    def add_user_to_organization(
            self, username, organization_id, role='editor'):

        # role=member|editor|admin
        self.remote.action.organization_member_create(
            id=str(organization_id), username=username, role=role)

    @CkanExceptionsHandler()
    def del_user_from_organization(self, username, organization_id):
        self.remote.action.organization_member_delete(
            id=str(organization_id), username=username)

    @CkanExceptionsHandler()
    def del_user_from_organizations(self, username):
        organizations = self.get_organizations_which_user_belongs(username)
        if not organizations:
            return
        for organization_name in organizations:
            self.del_user_from_organization(username, organization_name)

    @CkanExceptionsHandler()
    def get_group(self, group_name):
        return self.remote.action.group_show(id=group_name)

    @CkanExceptionsHandler()
    def add_group(self, group):
        self.remote.action.group_create(name=group.ckan_slug,
                                        title=group.name,
                                        description=group.description)
        return True

    @CkanExceptionsHandler()
    def del_group(self, group_name):
        self.remote.action.group_purge(id=group_name)

    @CkanExceptionsHandler()
    def add_user_to_group(self, username, group_name):
        group = self.get_group(group_name)
        if username not in [user['name'] for user in group['users']]:
            group['users'].append({'name': username, 'capacity': 'admin'})
        self.remote.action.group_update(**group)

    def sync_group(self, group):
        self.remote.action.group_update(
            id=group.ckan_slug, name=group.ckan_slug,
            title=group.name, description=group.description)
        return True

    @CkanExceptionsHandler()
    def purge_dataset(self, id):
        return self.remote.action.dataset_purge(id=id)

    @CkanExceptionsHandler()
    def get_tags(self, query=None):
        return self.remote.action.tag_list(query=query)


CkanHandler = CkanManagerHandler()
