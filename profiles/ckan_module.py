from ckanapi import RemoteCKAN
from ckanapi.errors import ValidationError, NotFound
from django.shortcuts import render
from django.conf import settings

import requests
import sys


def build_connector():
    return RemoteCKAN(settings.CKAN_URL, apikey=settings.CKAN_API_KEY)


def ckan_add_user(user, password):
    r = requests.post(settings.CKAN_URL + '/ldap_login_handler',
                      data = {'login':user.username, 'password':password})
    if not r.status_code == 200:
        # TODO: catch and return CKAN Exception
        raise Exception(r)

def ckan_del_user(username):
    ckan = build_connector()
    try:
        u = ckan.action.user_delete(id=username)
    except:
        pass
    return True


def ckan_add_organisation(org):
    ckan = build_connector()
    try:
       ckan.action.organization_create(id=org.ckan_slug, name=org.ckan_slug)
    except ValidationError:
        return False
    return True


def ckan_del_organisation(org):
    ckan = build_connector()
    try:
        ckan.action.organization_purge(id=org.ckan_slug)
    except NotFound:
        pass
    return True


def ckan_test_organisation(org):
    ckan = build_connector()
    try:
         ckan.action.organization_show(id=org.ckan_slug)
    except NotFound:
        return False
    return True


def ckan_user_deactivate(username):
    ckan = build_connector()
    try:
         ckan.action.user_update(id=org.ckan_slug)
    except NotFound:
        return False
    return True


def ckan_add_user_to_organisation(username, orgname):
    ckan = build_connector()
    ckan.action.member_create(id=orgname, object=username,
                              object_type='user', capacity='member')
    return True


def ckan_del_user_from_organisation(username, orgname):
    ckan = build_connector()
    ckan.action.member_delete(id=orgname, object=username, object_type='user')
    return True


def ckan_add_group(grp):

    ckan = build_connector()

    try:
        ckan.action.group_create(name=grp.ckan_slug, title=grp.name, description=grp.description)
    except ValidationError:
         return False
    return True

def ckan_sync_group(grp):

    ckan = build_connector()
    try:
         ckan.action.group_update(id=grp.ckan_slug, title=grp.name, description=grp.description)
    except ValidationError:
         return False
    return True

def ckan_del_group(grp):
    ckan = build_connector()
    try:
         ckan.action.group_purge(id=grp.ckan_slug)
    except ValidationError:
         return False
    return True