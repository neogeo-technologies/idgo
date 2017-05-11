import ldap
import passlib.hash
from datetime import datetime
from django.conf import settings
from profiles.get_current_request import get_current_user
from .utils import Singleton


class LdapHandler(metaclass=Singleton):

    LDAP_URL = settings.AUTH_LDAP_SERVER_URI
    LDAP_ACCOUNT = settings.AUTH_LDAP_BIND_DN
    LDAP_PASSWORD = settings.AUTH_LDAP_BIND_PASSWORD

    def __init__(self):
        self.conn = ldap.initialize(self.LDAP_URL, bytes_mode=False)
        self.conn.simple_bind_s(self.LDAP_ACCOUNT, self.LDAP_PASSWORD)

    def get_user(self, user):
        base = 'cn={0},ou=people,dc=idgo,dc=local'.format(user.username)
        try:
            return self.conn.search_s(base, ldap.SCOPE_SUBTREE)
        except ldap.NO_SUCH_OBJECT:
            return None

    def is_user_exists(self, user):
        return self.get_user(user) and True or False

    def add_user(self, user, password):

        gid = '{0}{1}'.format(settings.LDAP_PEOPLE_ID_INCREMENT, user.id)
        password = passlib.hash.ldap_sha1.encrypt(password)
        self.conn.add_s(
            'cn={0},ou=people,dc=idgo,dc=local'.format(user.username), [
                ("objectclass", [b"inetOrgPerson", b"posixAccount"]),
                ("uid", [user.username.encode()]),
                ("gidNumber", [gid.encode()]),
                ("uidNumber", [gid.encode()]),
                ("sn", [user.last_name.encode()]),
                ("givenName", [user.first_name.encode()]),
                ("displayName", [user.first_name.encode()]),
                ("mail", [user.email.encode()]),
                ("homeDirectory", ["/home/{0}".format(user.username).encode()]),
                ("userPassword", [password.encode()]),
                ("description", ["created by {0} at {1}".format(
                                "guillaume", datetime.now()).encode()])])

    def del_user(self, user):
        # TODO : delete user from all the groups he belongs to.
        try:
            self.conn.delete_s(
                    'cn={0},ou=people,dc=idgo,dc=local'.format(user.username))
        except:
            pass

    def add_user_to_group(self, user, group_dn):
        try:
            self.conn.modify_s(group_dn, [(ldap.MOD_ADD, "memberUid", user.username.encode())])
        except ldap.LDAPError as e:
            return False
        return True

    def del_user_from_group(self, user, group_dn):
        try:
            self.conn.modify_s(group_dn, [(ldap.MOD_DELETE, 'memberUid', user.username.encode())])
        except ldap.LDAPError:
            return False
        return True

    def create_object(self, object_type, object_name, gid, delete_first=False):
        u = get_current_user()
        dn = "cn=%s,ou=%s,dc=idgo,dc=local" % (object_name, object_type)
        self.conn.add_s(dn,[
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
                dn = result[0][0]
                self.conn.delete_s(dn)
                res = self.create_object(object_type, object_name, gid)
            res = True

        except ldap.NO_SUCH_OBJECT:
            res = False

        # finally:
        #     self.conn.unbind_s()

        return res


LdapHandler = LdapHandler()