import ldap
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

    def get_user(self, user_name):
        base = 'cn={0},ou=people,dc=idgo,dc=local'.format(user_name)
        try:
            return self.conn.search_s(base, ldap.SCOPE_SUBTREE)
        except ldap.NO_SUCH_OBJECT:
            return None

    def is_user_exists(self, user_name):
        return self.get_user(user_name) and True or False

    def add_user(self, user, password):

        gid = settings.LDAP_PEOPLE_ID_INCREMENT + user.id

        dn = "cn=%s,ou=people,dc=idgo,dc=local" % (user.username)
        homedir = "/home/{0}".format(user.username)
        try:
            self.conn.add_s(dn,[
                ("objectclass", [b"inetOrgPerson", b"posixAccount"]),
                ("uid", [user.username.encode()]),
                ("gidNumber", ["{0}".format(gid).encode()]),
                ("uidNumber", ["{0}".format(gid).encode()]),
                ("sn", [user.last_name.encode()]),
                ("givenName", [user.first_name.encode()]),
                ("displayName", [user.first_name.encode()]),
                ("mail", [user.email.encode()]),
                ("homeDirectory", [homedir.encode()]),
                ("userPassword", [password.encode()]),
                ("description", ["created by {0} at {1}".format(
                                    "guillaume", datetime.now()).encode()])])

        except ldap.LDAPError as e:
            # self.conn.unbind()
            raise e

        # self.conn.unbind_s()


    def del_user(self, uid):
        deleteDN = "cn=%s,ou=people,dc=idgo,dc=local" % uid
        # TODO : delete user from all the groups he belongs to.
        try:
            self.conn.delete_s(deleteDN)
        except:
            pass


    def add_user_to_group(self, uid, group_dn):
        # AJOUT AU GROUPE UTILISATEUR ADMIN
        modlist = []
        try:
            modlist.append((ldap.MOD_ADD, "memberUid", uid.encode()))
            self.conn.modify_s(group_dn, modlist)
        except ldap.LDAPError as e:
            return False
        return True


    def del_user_from_group(self, uid, group_dn):
        modlist = []
        try:
            modlist.append((ldap.MOD_DELETE, "memberUid", uid.encode()))
            self.conn.modify_s(group_dn, modlist)
        except ldap.LDAPError as e:
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
        res = False
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