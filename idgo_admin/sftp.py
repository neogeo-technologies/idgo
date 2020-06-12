#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import crypt
import json
import string
from secrets import choice

from django.conf import settings


taskfolder = getattr(settings, 'FTP_SERVICE_URL', '/WEBS/ternum/sftp.ternum.fr/neogeo-sftp/docs/ftp_tasks')


class SFTPError(Exception):
    """Base class for exceptions in this module."""
    pass


def password_generator():
    size=10
    alphabet = string.ascii_letters + string.digits + string.punctuation
    while True:
        password = ''.join(choice(alphabet) for i in range(size))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in string.punctuation for c in password)
        ):
            break
    return password


def write_command(login, command):
    h = open(os.path.join(taskfolder, "{}.json".format(login)), "w")
    h.write(json.dumps(command))
    h.close()



def sftp_user_operation(action, login):
    if not login:
        raise SFTPError("login required")
    if not action or action not in ["create", 'modify', "delete"]:
        raise SFTPError("unknonwn action '%s', should be 'create', 'modify' or 'delete'")

    if action in ["create", 'modify']:
        password = password_generator()
        encPass = crypt.crypt(password, crypt.METHOD_SHA512)

        create_command = {"command": action, "password": encPass}
        write_command(login, create_command)

        return password

    elif action == "delete":

        create_command = {"command":"delete"}
        write_command(login, create_command)


