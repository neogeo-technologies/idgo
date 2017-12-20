from ckanapi import errors as CkanError
from ckanapi import RemoteCKAN
from datetime import datetime
from django.conf import settings
from django.db import IntegrityError
from functools import wraps
from idgo_admin.exceptions import ConflictError
from idgo_admin.exceptions import GenericException
from idgo_admin.utils import Singleton
import timeout_decorator
from urllib.parse import urljoin


CKAN_URL = settings.CKAN_URL
CKAN_API_KEY = settings.CKAN_API_KEY
try:
    CKAN_TIMEOUT = settings.GEONET_TIMEOUT
except AttributeError:
    CKAN_TIMEOUT = 36000


def timeout(fun):
    t = CKAN_TIMEOUT  # in seconds

    @timeout_decorator.timeout(t, use_signals=False)
    def return_with_timeout(fun, args=tuple(), kwargs=dict()):
        return fun(*args, **kwargs)

    @wraps(fun)
    def wrapper(*args, **kwargs):
        return return_with_timeout(fun, args=args, kwargs=kwargs)

    return wrapper


class CkanSyncingError(GenericException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class CkanTimeoutError(CkanSyncingError):
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
                print('Error', e.__str__())
                if isinstance(e, timeout_decorator.TimeoutError):
                    raise CkanTimeoutError
                if self.is_ignored(e):
                    return f(*args, **kwargs)
                raise CkanSyncingError(e.__str__())
        return wrapper

    def is_ignored(self, exception):
        return type(exception) in self.ignore


class CkanUserHandler(object):

    def __init__(self, api_key):
        self.remote = RemoteCKAN(CKAN_URL, apikey=api_key)

    def close(self):
        self.remote.close()

    @timeout
    def call_action(self, action, **kwargs):
        return self.remote.call_action(action, kwargs)

    @CkanExceptionsHandler(ignore=[CkanError.NotFound])
    def get_package(self, id):
        try:
            return self.call_action(
                'package_show', id=id, include_tracking=True)
        except CkanError.NotFound:
            return False

    def is_package_exists(self, id):
        return self.get_package(id) and True or False

    def is_package_name_already_used(self, name):
        return self.get_package(name) and True or False

    @CkanExceptionsHandler()
    @timeout
    def push_resource(self, package, **kwargs):
        kwargs['package_id'] = package['id']
        kwargs['created'] = datetime.now().isoformat()
        for resource in package['resources']:
            if resource['id'] == kwargs['id']:
                kwargs['last_modified'] = kwargs['created']
                del kwargs['created']
                if 'url' in kwargs and not kwargs['url']:
                    del kwargs['url']
                resource.update(kwargs)
                del resource['tracking_summary']
                # Moche pour tester
                if resource['datastore_active']:
                    self.remote.action.resource_update(**resource)
                    if 'upload' in resource:
                        del resource['upload']
                # Fin de 'Moche pour tester'
                return self.remote.action.resource_update(**resource)
        return self.remote.action.resource_create(**kwargs)

    @CkanExceptionsHandler()
    def push_resource_view(self, **kwargs):
        kwargs['title'] = kwargs['title'] if 'title' in kwargs else 'Aperçu'
        kwargs['description'] = kwargs['description'] \
            if 'description' in kwargs else 'Aperçu du jeu de données'

        views = \
            self.call_action('resource_view_list', id=kwargs['resource_id'])
        for view in views:
            if view['view_type'] == kwargs['view_type']:
                return self.call_action(
                    'resource_view_update', id=view['id'], **kwargs)
        return self.call_action('resource_view_create', **kwargs)

    def check_dataset_integrity(self, name):
        if self.is_package_name_already_used(name):
            raise ConflictError('Dataset already exists')

    @CkanExceptionsHandler()
    def publish_dataset(self, name, id=None, resources=None, **kwargs):
        kwargs['name'] = name
        if id and self.is_package_exists(id):
            package = \
                self.call_action(
                    'package_update', **{**self.get_package(id), **kwargs})
        else:
            package = self.call_action('package_create', **kwargs)
        return package

    @CkanExceptionsHandler()
    def publish_resource(self, dataset_id, **kwargs):
        resource_view_type = kwargs['view_type'] or None
        del kwargs['view_type']
        resource = self.push_resource(self.get_package(dataset_id), **kwargs)
        if resource_view_type:
            self.push_resource_view(
                resource_id=resource['id'], view_type=resource_view_type)

    @CkanExceptionsHandler()
    def delete_resource(self, id):
        return self.call_action('resource_delete', id=id)

    @CkanExceptionsHandler()
    def delete_dataset(self, id):
        return self.call_action('package_delete', id=id)


class CkanManagerHandler(metaclass=Singleton):

    apikey = CKAN_API_KEY

    def __init__(self):
        self.remote = RemoteCKAN(CKAN_URL, apikey=self.apikey)

    @timeout
    def call_action(self, action, **kwargs):
        return self.remote.call_action(action, kwargs)

    def get_all_users(self):
        return [(user['name'], user['display_name'])
                for user in self.call_action('user_list')
                if user['state'] == 'active']

    @CkanExceptionsHandler(ignore=[CkanError.NotFound])
    def get_user(self, username):
        try:
            return self.call_action('user_show', id=username)
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
                  'activity_streams_email_notifications': True,
                  'state': 'deleted'}
        user = self.call_action('user_create', **params)

    @CkanExceptionsHandler()
    def del_user(self, username):
        # self.del_user_from_groups(username)
        self.del_user_from_organizations(username)
        self.call_action('user_delete', id=username)

    @CkanExceptionsHandler()
    def update_user(self, user):
        if not self.is_user_exists:
            raise IntegrityError(
                'User {0} does not exists'.format(user.username))

        ckan_user = self.get_user(user.username)
        ckan_user.update({'email': user.email,
                          'fullname': user.get_full_name()})
        self.call_action('user_update', **ckan_user)

    @CkanExceptionsHandler()
    def activate_user(self, username):
        ckan_user = self.get_user(username)
        ckan_user.update({'state': 'active'})
        self.call_action('user_update', **ckan_user)

    @CkanExceptionsHandler()
    def get_all_organizations(self):
        return [organization
                for organization in self.call_action('organization_list')]

    @CkanExceptionsHandler(ignore=[CkanError.NotFound])
    def get_organization(self, id, **kwargs):
        try:
            return self.call_action('organization_show', id=str(id), **kwargs)
        except CkanError.NotFound:
            return None

    def is_organization_exists(self, organization_id):
        return self.get_organization(str(organization_id)) and True or False

    @CkanExceptionsHandler(ignore=[ValueError])
    def add_organization(self, organization):
        params = {
            'id': str(organization.ckan_id),
            'name': organization.ckan_slug,
            'title': organization.name,
            'description': organization.description,
            'state': 'active'}
        try:
            params['image_url'] = \
                urljoin(settings.DOMAIN_NAME, organization.logo.url)
        except ValueError:
            pass
        self.call_action('organization_create', **params)

    @CkanExceptionsHandler()
    def update_organization(self, organization):
        ckan_organization = \
            self.get_organization(organization.ckan_id, include_datasets=True)

        ckan_organization.update({
            'title': organization.name,
            'name': organization.ckan_slug,
            'description': organization.description})

        try:
            ckan_organization['image_url'] = \
                urljoin(settings.DOMAIN_NAME, organization.logo.url)
        except ValueError:
            pass

        self.call_action('organization_update', **ckan_organization)

        for package in ckan_organization['packages']:
            self.call_action('package_owner_org_update', id=package['id'],
                             organization_id=ckan_organization['id'])

    @CkanExceptionsHandler()
    def purge_organization(self, id):
        return self.call_action('organization_purge', id=id)

    @CkanExceptionsHandler()
    def activate_organization(self, id):
        self.call_action('organization_update', id=id, state='active')

    @CkanExceptionsHandler()
    def deactivate_organization(self, id):
        self.call_action('organization_update', id=id, state='deleted')

    @CkanExceptionsHandler()
    def del_organization(self, id):
        self.call_action('organization_purge', id=str(id))

    @CkanExceptionsHandler()
    def get_organizations_which_user_belongs(
            self, username, permission='manage_group'):
        # permission=read|create_dataset|manage_group
        res = self.call_action(
            'organization_list_for_user', id=username, permission=permission)
        return [d['name'] for d in res if d['is_organization']]

    @CkanExceptionsHandler()
    def add_user_to_organization(
            self, username, organization_id, role='editor'):
        # role=member|editor|admin
        self.call_action(
            'organization_member_create',
            id=str(organization_id), username=username, role=role)

    @CkanExceptionsHandler()
    def del_user_from_organization(self, username, organization_id):
        self.call_action(
            'organization_member_delete',
            id=str(organization_id), username=username)

    @CkanExceptionsHandler()
    def del_user_from_organizations(self, username):
        organizations = self.get_organizations_which_user_belongs(username)
        if not organizations:
            return
        for organization_name in organizations:
            self.del_user_from_organization(username, organization_name)

    @CkanExceptionsHandler(ignore=[CkanError.NotFound])
    def get_group(self, id, **kwargs):
        try:
            return self.call_action('group_show', id=str(id), **kwargs)
        except CkanError.NotFound:
            return None

    def is_group_exists(self, id):
        return self.get_group(str(id)) and True or False

    @CkanExceptionsHandler()
    def add_group(self, group, type=None):
        ckan_group = {
            'id': str(group.ckan_id),
            'type': type,
            'title': group.name,
            'name': group.ckan_slug,
            'description': group.description}
        try:
            ckan_group['image_url'] = \
                urljoin(settings.DOMAIN_NAME, group.picto.url)
        except ValueError:
            pass
        return self.call_action('group_create', **ckan_group)

    @CkanExceptionsHandler()
    def update_group(self, group):
        ckan_group = self.get_group(str(group.ckan_id), include_datasets=True)
        ckan_group.update({
            'title': group.name,
            'name': group.ckan_slug,
            'description': group.description})

        for val in ('packages', 'tags', 'groups'):
            lst = ckan_group.get(val, [])
            if lst:
                del ckan_group[val]
            ckan_group[val] = [{'id': e['id'], 'name': e['name']} for e in lst]

        try:
            ckan_group['image_url'] = \
                urljoin(settings.DOMAIN_NAME, group.picto.url)
        except ValueError:
            pass
        try:
            return self.call_action('group_update', **ckan_group)
        except CkanError.NotFound:
            return None

    @CkanExceptionsHandler()
    def del_group(self, id):
        self.call_action('group_purge', id=str(id))

    @CkanExceptionsHandler()
    def add_user_to_group(self, username, group_id):
        ckan_group = self.get_group(str(group_id), include_datasets=True)
        if not ckan_group:
            raise Exception("The group '{0}' does not exists".format(str(group_id)))

        packages = ckan_group.get('packages', [])
        if packages:
            del ckan_group['packages']
        ckan_group['packages'] = \
            [{'id': package['id'], 'name': package['name']} for package in packages]

        users = ckan_group.get('users', [])
        if users:
            del ckan_group['users']
        ckan_group['users'] = \
            [{'id': user['id'], 'name': user['name'], 'capacity': 'admin'} for user in users]

        if username not in [user['name'] for user in ckan_group['users']]:
            ckan_group['users'].append({'name': username, 'capacity': 'admin'})

        self.call_action('group_update', **ckan_group)

    @CkanExceptionsHandler()
    def purge_dataset(self, id):
        return self.call_action('dataset_purge', id=id)

    @CkanExceptionsHandler()
    def get_tags(self, query=None, all_fields=False, vocabulary_id=None):
        return self.call_action('tag_list', vocabulary_id=vocabulary_id,
                                all_fields=all_fields, query=query)

    def is_tag_exists(self, name, vocabulary_id=None):
        try:
            return name in self.get_tags(vocabulary_id=vocabulary_id)
        except Exception:
            return False

    @CkanExceptionsHandler()
    def add_tag(self, name, vocabulary_id=None):
        return self.call_action(
            'tag_create', name=name, vocabulary_id=vocabulary_id)

    @CkanExceptionsHandler()
    def add_vocabulary(self, name, tags):
        return self.call_action('vocabulary_create', name=name,
                                tags=[{'name': tag} for tag in tags])

    @CkanExceptionsHandler()
    def get_vocabulary(self, id):
        try:
            return self.call_action('vocabulary_show', id=id)
        except CkanError.NotFound:
            return None

    @CkanExceptionsHandler()
    def get_licenses(self):
        return self.call_action('license_list')


CkanHandler = CkanManagerHandler()
