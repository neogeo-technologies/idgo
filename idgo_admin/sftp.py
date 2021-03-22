# Copyright (c) 2017-2021 Neogeo-Technologies.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


import os
import crypt
import json
import string
from secrets import choice

from idgo_admin import FTP_SERVICE_URL


class SFTPError(Exception):
    """Base class for exceptions in this module."""


def password_generator():
    size = 10
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
    h = open(os.path.join(FTP_SERVICE_URL, '{}.json'.format(login)), "w")
    h.write(json.dumps(command))
    h.close()


def sftp_user_operation(action, login):
    if not login:
        raise SFTPError("Login required")
    if not action or action not in ['create', 'modify', 'delete']:
        raise SFTPError("Unknonwn action '%s'. Should be 'create', 'modify' or 'delete'")

    if action in ['create', 'modify']:
        password = password_generator()
        encPass = crypt.crypt(password, crypt.METHOD_SHA512)

        create_command = {'command': action, 'password': encPass}
        write_command(login, create_command)

        return password

    elif action == 'delete':

        create_command = {'command': 'delete'}
        write_command(login, create_command)
