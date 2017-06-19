import ldap
import passlib.hash
from datetime import datetime
from django.conf import settings
from django.db import IntegrityError
from profiles.get_current_request import get_current_user
from .utils import Singleton


class LdapHandler(metaclass=Singleton):

    LDAP_URL = settings.AUTH_LDAP_SERVER_URI
    LDAP_ACCOUNT = settings.AUTH_LDAP_BIND_DN
    LDAP_PASSWORD = settings.AUTH_LDAP_BIND_PASSWORD

    def __init__(self):
        self.conn = ldap.initialize(self.LDAP_URL, bytes_mode=False)
        self.conn.simple_bind_s(self.LDAP_ACCOUNT, self.LDAP_PASSWORD)

    def _search(self, base_dn, filterstr='(objectClass=*)', attrlist=None):
        try:
            return self.conn.search_s(base_dn, ldap.SCOPE_SUBTREE,
                                      filterstr=filterstr, attrlist=attrlist)
        except ldap.NO_SUCH_OBJECT as e:
            return None
        except ldap.LDAPError as e:
            print('~> base_dn:', base_dn)
            print('~> filterstr:', filterstr)
            print('~> catching error:', e)
            raise e

    def _modify(self, base_dn, modlist):
        try:
            self.conn.modify_s(base_dn, modlist)
        except ldap.TYPE_OR_VALUE_EXISTS as e:
            print('TYPE_OR_VALUE_EXISTS', e)
            return None
        except ldap.NO_SUCH_OBJECT as e:
            print('NO_SUCH_OBJECT', e)
            return None
        except ldap.NO_SUCH_ATTRIBUTE as e:
            print('NO_SUCH_ATTRIBUTE', e)
            return None
        except ldap.LDAPError as e:
            print('~> base_dn:', base_dn)
            print('~> modlist:', modlist)
            print('~> catching error:', e)
            raise e

    def get_user(self, username):

        res = self._search('cn={0},ou=people,dc=idgo,dc=local'.format(username))
        if res is None:
            return None
        if len(res) > 1:  # TODO???
            raise IntegrityError()
        return res[0]

    def is_user_exists(self, username):
        return self.get_user(username) and True or False

    def add_user(self, user, password):

        gid = '{0}{1}'.format(settings.LDAP_PEOPLE_ID_INCREMENT, user.id)
        password = passlib.hash.ldap_sha1.encrypt(password)
        self.conn.add_s(
            'cn={0},ou=people,dc=idgo,dc=local'.format(user.username), [
                ('objectclass', [b"inetOrgPerson", b"posixAccount"]),
                ('uid', [user.username.encode()]),
                ('gidNumber', [gid.encode()]),
                ('uidNumber', [gid.encode()]),
                ('sn', [user.last_name.encode()]),
                ('givenName', [user.first_name.encode()]),
                ('displayName', [user.get_full_name().encode()]),
                ('mail', [user.email.encode()]),
                ('homeDirectory', ['/home/{0}'.format(user.username).encode()]),
                ('userPassword', [password.encode()]),
                ('description', ['created by {0} at {1}'.format(
                                            'idgo', datetime.now()).encode()])])

    def del_user(self, username):

        self.del_user_from_groups(username)
        self.del_user_from_organizations(username)
        self.conn.delete_s('cn={0},ou=people,dc=idgo,dc=local'.format(username))

    def update_user(self, user, password=None, profile=None):

        if not self.is_user_exists:
            raise IntegrityError()

        base_dn, moddict = self.get_user(user.username)

        attrs = [('displayName', [user.get_full_name()]),
                 ('givenName', [user.first_name]),
                 ('mail', [user.email]),
                 ('sn', [user.last_name])]

        if password:
            attrs.append(
                ('userPassword', [passlib.hash.ldap_sha1.encrypt(password)]))

        if profile:
            self.del_user_from_organizations(user.username)

            # Todo orga a null en modification
            if profile.organisation:
                self.add_user_to_organization(
                                user.username, profile.organisation.ckan_slug)

        modlist = []
        for m in attrs:
            k = m[0]
            modlist.append((ldap.MOD_DELETE, k, moddict[k]))
            modlist.append((ldap.MOD_ADD, k, [e.encode() for e in m[1]]))

        self._modify(base_dn, modlist)

    def activate_user(self, username):
        self.add_user_to_group(username, 'active')

    def get_groups_which_user_belongs(self, username):

        res = self._search('ou=groups,dc=idgo,dc=local',
                           filterstr='(memberUid={0})'.format(username),
                           attrlist=['cn'])
        return res and [e[1]['cn'][0].decode() for e in res] or []

    def add_user_to_group(self, username, group_name):
        self._modify('cn={0},ou=groups,dc=idgo,dc=local'.format(group_name),
                     [(ldap.MOD_ADD, 'memberUid', username.encode())])

    def del_user_from_group(self, username, group_name):
        self._modify('cn={0},ou=groups,dc=idgo,dc=local'.format(group_name),
                     [(ldap.MOD_DELETE, 'memberUid', username.encode())])

    def del_user_from_groups(self, username):

        groups = self.get_groups_which_user_belongs(username)
        for group_name in groups:
            self.del_user_from_group(username, group_name)

    def get_organization(self, organization_name):
        res = self._search('cn={0},ou=organisations,dc=idgo,dc=local'.format(
                                                            organization_name))
        if res is None:
            return None
        if len(res) > 1:  # TODO???
            raise IntegrityError()
        return res[0]

    def is_organization_exists(self, organization_name):
        return self.get_organization(organization_name) and True or False

    def add_organization(self, organization):
        self.conn.add_s(
            'cn=%s,ou=organisations,dc=idgo,dc=local'.format(user.username), [
                ('objectclass', [b"posixGroup"]),
                # ('gidNumber', [gid.encode()]),
                ('description', ['created by {0} at {1}'.format(
                                            'idgo', datetime.now()).encode()])])

    def del_organization(self, organization_name):
        pass #TODO

    def get_organizations_which_user_belongs(self, username):

        res = self._search('ou=organisations,dc=idgo,dc=local',
                           filterstr='(memberUid={0})'.format(username),
                           attrlist=['cn'])
        return res and [e[1]['cn'][0].decode() for e in res] or []

    def add_user_to_organization(self, username, organization_name):

        self._modify(
            'cn={0},ou=organisations,dc=idgo,dc=local'.format(organization_name),
            [(ldap.MOD_ADD, 'memberUid', username.encode())])

    def del_user_from_organization(self, username, organization_name):

        self._modify(
            'cn={0},ou=organisations,dc=idgo,dc=local'.format(organization_name),
            [(ldap.MOD_DELETE, 'memberUid', username.encode())])

    def del_user_from_organizations(self, username):
        organizations = self.get_organizations_which_user_belongs(username)
        if not organizations:
            return
        for organization_name in organizations:
            self.del_user_from_organization(username, organization_name)

    ###

    def create_object(self, object_type, object_name, gid, delete_first=False):

        u = get_current_user()
        base_dn = "cn=%s,ou=%s,dc=idgo,dc=local" % (object_name, object_type)
        self.conn.add_s(base_dn,[
            ("objectclass", [b"posixGroup"]),
            ("gidNumber", ["{0}".format(gid).encode()]),
            ("description", ["created by {0} at {1}".format(
                                        u.username, datetime.now()).encode()])])
        return True

    def sync_object(self, object_type, object_name, gid, operation='add_or_update'):

        try:
            result = self.conn.search_s('ou=%s,dc=idgo,dc=local' % object_type,
                                     ldap.SCOPE_SUBTREE, "(gidNumber=%s)" % gid)
            if operation == 'delete' and len(result) == 1:
                res = self.conn.delete_s(result[0][0])
            elif operation == 'add_or_update' and len(result) == 0:
                res = self.create_object(object_type, object_name, gid)
            elif operation == 'add_or_update' and len(result) == 1:
                base_dn = result[0][0]
                self.conn.delete_s(base_dn)
                res = self.create_object(object_type, object_name, gid)
            res = True

        except ldap.NO_SUCH_OBJECT:
            res = False

        # finally:
        #     self.conn.unbind_s()

        return res


LdapHandler = LdapHandler()
