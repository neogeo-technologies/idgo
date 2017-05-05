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

    def add_user(self, login, password):
        r = requests.post('{0}/ldap_login_handler'.format(settings.CKAN_URL),
                          data={'login': login, 'password': password})

        if not r.status_code == 200:
            raise Exception(r)  # TODO

    def del_user(self, user_name):
        self.remote.action.user_delete(id=user_name)

    def deactivate_user(self, user_name):
        try:
            self.remote.action.user_update(id=user_name)
        except NotFound:
            pass

    def add_organization(self, organization):

        params = {'id': organization.ckan_slug,
                  'name': organization.name}

        self.remote.action.organization_create(**params)

    def del_organization(self, organization):

        params = {'id': organization.ckan_slug}

        try:
            self.remote.action.organization_purge(**params)
        except NotFound as e:
            pass

    def test_organization(self, organization):

        params = {'id': organization.ckan_slug}

        try:
            self.remote.action.organization_show(**params)
        except NotFound:
            pass

    def add_user_to_organization(self, user_name, organization):

        params = {'id': organization.ckan_slug,
                  'object_type': 'user',
                  'object': user_name,
                  'capacity': 'member'}

        self.remote.action.member_create(**params)

    def del_user_from_organization(self, user_name, organization):

        params = {'id': organization.ckan_slug,
                  'object_type': 'user',
                  'object': user_name}

        self.remote.action.member_delete(**params)

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
