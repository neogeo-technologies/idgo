from django.conf import settings
from django.contrib.sessions.models import Session
from django.contrib.auth.models import User

from profiles.get_current_request import get_current_user

import ldap
import ldap.modlist as modlist
import datetime

LDAP_URL = settings.AUTH_LDAP_SERVER_URI
LDAP_ACCOUNT = settings.AUTH_LDAP_BIND_DN
LDAP_PASSWORD = settings.AUTH_LDAP_BIND_PASSWORD


def get_ldap():
    l = ldap.initialize(LDAP_URL, bytes_mode=False)
    l.simple_bind_s(LDAP_ACCOUNT, LDAP_PASSWORD)
    return l


def ldap_add_user(user, password):
    l = get_ldap()

    gid = settings.LDAP_PEOPLE_ID_INCREMENT + user.id

    dn = "cn=%s,ou=people,dc=idgo,dc=local" % (user.username)
    homedir = "/home/{0}".format(user.username)
    try:
        l.add_s(dn,[
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
            ("description", ["created by {0} at {1}".format("guillaume", datetime.datetime.now()).encode()])])
    except ldap.LDAPError as e:
        l.unbind()
        raise e

    l.unbind_s()


def ldap_del_user(uid):
    l = get_ldap()
    deleteDN = "cn=%s,ou=people,dc=idgo,dc=local" % uid
    # TODO : delete user from all the groups he belongs to.
    try:
        l.delete_s(deleteDN)
    except:
        pass


def ldap_add_user_to_group(uid, group_dn):
    # AJOUT AU GROUPE UTILISATEUR ADMIN
    l = get_ldap()
    modlist = []
    try:
        modlist.append((ldap.MOD_ADD, "memberUid", uid.encode()))
        l.modify_s(group_dn, modlist)
    except ldap.LDAPError as e:
        print(e)
        return False
    True


def ldap_del_user_from_group(uid, group_dn):
    l = get_ldap()
    modlist = []
    try:
        modlist.append((ldap.MOD_DELETE, "memberUid", uid.encode()))
        l.modify_s(group_dn, modlist)
    except ldap.LDAPError as e:
        print(e)
        return False
    True


def create_object(l, object_type, object_name, gid, delete_first=False):
    u = get_current_user()
    dn = "cn=%s,ou=%s,dc=idgo,dc=local" % (object_name, object_type)
    l.add_s(dn,
            [
                ("objectclass", [b"posixGroup"]),
                ("gidNumber", ["{0}".format(gid).encode()]),
                ("description", ["created by {0} at {1}".format(u.username,
                                                                datetime.datetime.now()).encode()])
            ]
            )
    return True


def ldap_sync_object(object_type, object_name, gid, operation='add_or_update'):
    l = get_ldap()
    res = False
    try:
        result = l.search_s('ou=%s,dc=idgo,dc=local' % object_type,
                            ldap.SCOPE_SUBTREE, "(gidNumber=%s)" % gid)
        if operation == 'delete' and len(result) == 1:
            res = l.delete_s(result[0][0])
        elif operation == 'add_or_update' and len(result) == 0:
            res = create_object(l, object_type, object_name, gid)
        elif operation == 'add_or_update' and len(result) == 1:
            dn = result[0][0]
            l.delete_s(dn)
            res = create_object(l, object_type, object_name, gid)
        res = True

    except ldap.NO_SUCH_OBJECT:
        res = False

    finally:
        l.unbind_s()
    return res
