from ckanapi import RemoteCKAN
from ckanapi.errors import NotFound
from django.conf import settings
from .utils import Singleton

import requests


class CkanHandler(metaclass=Singleton):

    API_KEY = settings.CKAN_API_KEY
    URL = settings.CKAN_URL

    def __init__(self):
        self.remote = RemoteCKAN(self.URL, apikey=self.API_KEY)

    def get_user(self, user):
        try:
            return self.remote.action.user_show(id=user.username)
        except NotFound:
            return None

    def is_user_exists(self, user):

        return self.get_user(user) and True or False

    def add_user(self, user, password):

        r = requests.post('{0}/ldap_login_handler'.format(settings.CKAN_URL),
                          data={'login': user.username, 'password': password})

        if r.status_code != 200:
            raise Exception()

        self.remote.action.user_update(
                id=user.username, name=user.username, email=user.email,
                fullname='{0} {1}'.format(user.first_name, user.last_name),
                state='deleted')

    def activate_user(self, user):
        return self.remote.action.user_update(id=user.username, state='active')

    def del_user(self, user):
        try:
            return self.remote.action.user_delete(id=user.username)
        except NotFound:
            return None

    def add_organization(self, organization):
        params = {'id': organization.ckan_slug, 'name': organization.name}
        self.remote.action.organization_create(**params)

    def del_organization(self, organization):
        params = {'id': organization.ckan_slug}
        try:
            self.remote.action.organization_purge(**params)
        except NotFound:
            pass

    def test_organization(self, organization):
        params = {'id': organization.ckan_slug}
        try:
            self.remote.action.organization_show(**params)
        except NotFound:
            pass

    def add_user_to_organization(self, user, organization):
        params = {'id': organization.ckan_slug,
                  'username': user.username,
                  'role': 'member'}
        self.remote.action.organization_member_create(**params)

    def del_user_from_organization(self, user, organization):
        params = {'id': organization.ckan_slug, 'username': user.username}
        self.remote.action.organization_member_delete(**params)

    def add_group(self, group):
        params = {'name': group.ckan_slug,
                  'title': group.name,
                  'description': group.description}
        self.remote.action.group_create(**params)

    def del_group(self, group):
        self.remote.action.group_purge(id=group.ckan_slug)

    def sync_group(self, group):
        params = {'name': group.ckan_slug,
                  'title': group.name,
                  'description': group.description}
        self.remote.action.group_update(**params)


CkanHandler = CkanHandler()
