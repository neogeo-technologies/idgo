import requests
from ckanapi import RemoteCKAN
from ckanapi.errors import NotFound
from django.conf import settings
from django.db import IntegrityError
from .utils import Singleton


class CkanHandler(metaclass=Singleton):

    API_KEY = settings.CKAN_API_KEY
    URL = settings.CKAN_URL

    def __init__(self):
        self.remote = RemoteCKAN(self.URL, apikey=self.API_KEY)

    def get_user(self, username):
        try:
            return self.remote.action.user_show(id=username)
        except NotFound:
            return None

    def is_user_exists(self, username):
        return self.get_user(username) and True or False

    def add_user(self, user, password):

        r = requests.post('{0}/ldap_login_handler'.format(settings.CKAN_URL),
                          data={'login': user.username, 'password': password})

        if r.status_code == 200:
            pass
        elif r.status_code == 500:
            raise SystemError('CKAN returns an internal error.')
        else:
            raise Exception(
                        'CKAN returns a {0} code error.'.format(r.status_code))

        self.remote.action.user_update(
                id=user.username, name=user.username, email=user.email,
                fullname=user.get_full_name(),
                state='deleted')

    def del_user(self, username):

        # self.del_user_from_groups(username)
        self.del_user_from_organizations(username)
        self.remote.action.user_delete(id=username)

    def update_user(self, user, profile=None):

        if not self.is_user_exists:
            raise IntegrityError()

        if profile:
            self.del_user_from_organizations(user.username)
            self.add_user_to_organization(
                            user.username, profile.organisation.ckan_slug)

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
        except NotFound:
            return None

    def is_organization_exists(self, organization_name):
        return self.get_organization(organization_name) and True or False

    def add_organization(self, organization):
        self.remote.action.organization_create(id=organization.ckan_slug,
                                               name=organization.name)

    def del_organization(self, organization_name):
        self.remote.action.organization_purge(id=organization_name)

    def get_organizations_which_user_belongs(
                        self, username, permission='manage_group'):

        # permission=read|create_dataset|manage_group
        res = self.remote.action.organization_list_for_user(
                                            id=username, permission=permission)
        return [d['name'] for d in res if d['is_organization']]

    def add_user_to_organization(
                        self, username, organization_name, role='member'):

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

    ###

    def add_group(self, group):
        self.remote.action.group_create(name=group.ckan_slug,
                                        title=group.name,
                                        description=group.description)

    def del_group(self, group_name):
        self.remote.action.group_purge(id=group_name)

    def sync_group(self, group):
        self.remote.action.group_update(name=group.ckan_slug,
                                        title=group.name,
                                        description=group.description)


CkanHandler = CkanHandler()
