from ckanapi import errors as CkanError
from ckanapi import RemoteCKAN
from datetime import datetime
from django.conf import settings
from django.db import IntegrityError
from functools import wraps
from idgo_admin.utils import Singleton


CKAN_URL = settings.CKAN_URL
CKAN_API_KEY = settings.CKAN_API_KEY


def exceptions_handler(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except CkanError.NotAuthorized as e:
            print('CkanError', e.__str__())
            raise PermissionError('CkanError.NotAuthorized', e.__str__())
        except CkanError.ValidationError as e:
            print('CkanError', e.__str__())
            raise Exception('CkanError.ValidationError', e.__str__())
        except CkanError.NotFound as e:
            print('CkanError', e.__str__())
            raise Exception('CkanError.NotFound', e.__str__())
        except CkanError.SearchQueryError as e:
            print('CkanError', e.__str__())
            raise Exception('CkanError.SearchQueryError', e.__str__())
        except CkanError.SearchError as e:
            print('CkanError', e.__str__())
            raise Exception('CkanError.SearchError', e.__str__())
        except CkanError.SearchIndexError as e:
            print('CkanError', e.__str__())
            raise Exception('CkanError.SearchIndexError', e.__str__())
    return wrapper


class CkanManagerHandler(metaclass=Singleton):

    def __init__(self):
        self.remote = RemoteCKAN(CKAN_URL, apikey=CKAN_API_KEY)

    @exceptions_handler
    def _del_package(self, id):
        return self.remote.action.dataset_purge(id=id)

    def get_user(self, username):
        try:
            return self.remote.action.user_show(id=username)
        except CkanError.NotFound:
            return None

    def is_user_exists(self, username):
        return self.get_user(username) and True or False

    def add_user(self, user, password):

        params = {'email': user.email,
                  'fullname': user.get_full_name(),
                  'name': user.username,
                  'password': password,
                  'state': 'deleted'}
        try:
            user = self.remote.action.user_create(**params)
        except Exception as e:
            raise Exception(e)

        # r = requests.post('{0}/ldap_login_handler'.format(settings.CKAN_URL),
        #                   data={'login': user.username, 'password': password})
        #
        # if r.status_code == 200:
        #     pass
        # elif r.status_code == 500:
        #     raise SystemError('CKAN returns an internal error.')
        # else:
        #     raise Exception(
        #         'CKAN returns a {0} code error.'.format(r.status_code))
        #
        # self.remote.action.user_update(
        #     id=user.username, name=user.username, email=user.email,
        #     fullname=user.get_full_name(), state='deleted')

    def del_user(self, username):

        # self.del_user_from_groups(username)
        self.del_user_from_organizations(username)
        self.remote.action.user_delete(id=username)

    def update_user(self, user, profile=None):

        if not self.is_user_exists:
            raise IntegrityError()

        # if profile:
        #     self.del_user_from_organizations(user.username)
        #     if profile.organisation:
        #         self.add_user_to_organization(
        #             user.username, profile.organisation.ckan_slug)

        ckan_user = self.get_user(user.username)

        ckan_user.update({'email': user.email,
                          'fullname': user.get_full_name()})

        self.remote.action.user_update(**ckan_user)

    def activate_user(self, username):
        ckan_user = self.get_user(username)
        ckan_user.update({'state': 'active'})
        self.remote.action.user_update(**ckan_user)

    def get_organization(self, organization_name):
        try:
            self.remote.action.organization_show(id=organization_name)
        except CkanError.NotFound:
            return None

    def is_organization_exists(self, organization_name):
        return self.get_organization(organization_name) and True or False

    def add_organization(self, organization):
        self.remote.action.organization_create(name=organization.ckan_slug,
                                               title=organization.name)

    def del_organization(self, organization_name):
        self.remote.action.organization_purge(id=organization_name)

    def get_organizations_which_user_belongs(
            self, username, permission='manage_group'):

        # permission=read|create_dataset|manage_group
        res = self.remote.action.organization_list_for_user(
            id=username, permission=permission)
        return [d['name'] for d in res if d['is_organization']]

    def add_user_to_organization(
            self, username, organization_name, role='editor'):

        # role=member|editor|admin
        self.remote.action.organization_member_create(
            id=organization_name, username=username, role=role)

    def del_user_from_organization(self, username, organization_name):
        self.remote.action.organization_member_delete(
            id=organization_name, username=username)

    def del_user_from_organizations(self, username):
        organizations = self.get_organizations_which_user_belongs(username)
        if not organizations:
            return
        for organization_name in organizations:
            self.del_user_from_organization(username, organization_name)

    def get_group(self, group_name):
        return self.remote.action.group_show(id=group_name)

    def add_group(self, group):
        self.remote.action.group_create(name=group.ckan_slug,
                                        title=group.name,
                                        description=group.description)
        return True

    def del_group(self, group_name):
        self.remote.action.group_purge(id=group_name)

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

    def purge_dataset(self, id):
        self._del_package(id)

    def get_tags(self, query=None):
        return self.remote.action.tag_list(query=query)


class CkanUserHandler(object):

    def __init__(self, api_key):

        self.remote = RemoteCKAN(CKAN_URL, apikey=api_key)

    def close(self):
        self.remote.close()

    def _get_package(self, id):
        try:
            return self.remote.action.package_show(
                id=id, include_tracking=True)
        except CkanError.NotFound:
            return False

    def _is_package_exists(self, id):
        return self._get_package(id) and True or False

    @exceptions_handler
    def _add_package(self, **kwargs):
        return self.remote.action.package_create(**kwargs)

    @exceptions_handler
    def _update_package(self, **kwargs):
        return self.remote.action.package_update(**kwargs)

    @exceptions_handler
    def _del_package(self, id):
        return self.remote.action.package_delete(id=id)

    @exceptions_handler
    def _push_resource(self, package, **kwargs):
        kwargs['package_id'] = package['id']
        kwargs['created'] = datetime.now().isoformat()
        for resource in package['resources']:
            if resource['id'] == kwargs['id']:
                kwargs['last_modified'] = kwargs['created']
                del kwargs['created']
                resource.update(kwargs)
                return self.remote.action.resource_update(**resource)
        return self.remote.action.resource_create(**kwargs)

    @exceptions_handler
    def _del_resource(self, id):
        return self.remote.action.resource_delete(id=id)

    @exceptions_handler
    def _push_resource_view(self, **kwargs):

        kwargs['title'] = kwargs['title'] if 'title' in kwargs else 'Aperçu'
        kwargs['description'] = kwargs['description'] \
            if 'description' in kwargs else 'Aperçu du jeu de données'

        views = self.remote.action.resource_view_list(id=kwargs['resource_id'])
        for view in views:
            print('Update view ->', view)
            if view['view_type'] == kwargs['view_type']:
                return self.remote.action.resource_view_update(id=view['id'],
                                                               **kwargs)
        print('Create view ->', kwargs)
        return self.remote.action.resource_view_create(**kwargs)

    def publish_dataset(self, name, id=None, resources=None, **kwargs):
        kwargs['name'] = name

        if id and self._is_package_exists(id):
            package = self._update_package(
                **{**self._get_package(id), **kwargs})
        else:
            package = self._add_package(**kwargs)

        return package

    def publish_resource(self, dataset_id, **kwargs):
        resource = self._push_resource(self._get_package(dataset_id), **kwargs)
        params = {
            'resource_id': resource['id'],
            'view_type': {
                'csv': 'recline_view',
                'json': 'text_view',
                'wms': 'geo_view',
                'xls': 'recline_view',
                'xml': 'text_view'
                }.get(kwargs['format'], 'text_view')}
        self._push_resource_view(**params)

    def delete_resource(self, id):
        self._del_resource(id)

    def delete_dataset(self, id):
        self._del_package(id)


CkanHandler = CkanManagerHandler()
