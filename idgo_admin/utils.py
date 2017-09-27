from decimal import Decimal
from django.conf import settings
from idgo_admin.exceptions import SizeLimitExceededError
import json
import os
import re
import requests
import shutil
import string
from urllib.parse import urlparse
from uuid import uuid4
import phonenumbers

STATIC_ROOT = settings.STATIC_ROOT
STATICFILES_DIRS = settings.STATICFILES_DIRS


# Metaclasses:


class StaticClass(type):
    def __call__(cls):
        raise TypeError(
            "'{0}' static class is not callable.".format(cls.__qualname__))


class Singleton(type):

    __instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls.__instances:
            cls.__instances[cls] = super().__call__(*args, **kwargs)
        # else:
        #     cls._instances[cls].__init__(*args, **kwargs)
        return cls.__instances[cls]


# Others stuffs


def create_dir(media_root):
    directory = os.path.join(media_root, str(uuid4())[:7])
    if not os.path.exists(directory):
        os.makedirs(directory)
        return directory
    return create_dir(media_root)


def remove_dir(directory):
    if not os.path.exists(directory):
        return
    shutil.rmtree(directory)


def download(url, media_root, **kwargs):

    def get_content_header_param(txt, param):
        found = re.search('{0}="([^;"\n\r\t\0\s\X\R\v]+)"'.format(param), txt)
        if found:
            return found.groups()[0]

    max_size = kwargs.get('max_size')

    for i in range(0, 10):  # Try at least ten times before raise
        try:
            r = requests.get(url, stream=True)
        except Exception as e:
            error = e
            continue
        else:
            break
    else:
        raise error
    r.raise_for_status()

    if r.headers.get('Content-Length', 0) > max_size:
        raise SizeLimitExceededError(max_size=max_size)

    directory = create_dir(media_root)
    filename = os.path.join(
        directory,
        get_content_header_param(r.headers.get('Content-Disposition'), 'filename')
        or urlparse(url).path.split('/')[-1]
        or 'file')

    # TODO(@m431m) -> https://github.com/django/django/blob/3c447b108ac70757001171f7a4791f493880bf5b/docs/topics/files.txt#L120

    with open(filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
            if os.fstat(f.fileno()).st_size > max_size:
                remove_dir(directory)
                raise SizeLimitExceededError(max_size=max_size)

    return filename, r.headers['Content-Type']


class PartialFormatter(string.Formatter):
    def __init__(self, missing='~~', bad_fmt='!!'):
        self.missing, self.bad_fmt = missing, bad_fmt

    def get_field(self, field_name, args, kwargs):
        # Handle a key not found
        try:
            val = super(PartialFormatter, self).get_field(field_name, args, kwargs)
            # Python 3, 'super().get_field(field_name, args, kwargs)' works
        except (KeyError, AttributeError):
            val = None, field_name
        return val

    def format_field(self, value, spec):
        # handle an invalid format
        if not value:
            return self.missing
        try:
            return super(PartialFormatter, self).format_field(value, spec)
        except ValueError:
            if self.bad_fmt:
                return self.bad_fmt
            else:
                raise


def three_suspension_points(val, max_len=19):
    return (len(val)) > max_len and val[0:max_len - 3] + '...' or val


def readable_file_size(val):
    l = len(str(val))
    if l > 6:
        return '{0} mo'.format(Decimal(int(val) / 1024 / 1024))
    elif l > 3:
        return '{0} ko'.format(Decimal(int(val) / 1024))
    else:
        return '{0} octets'.format(int(val))


def open_json_staticfile(filename):
    def open_json(root):
        with open(os.path.join(root, filename), encoding='utf-8') as f:
            return json.load(f)

    if STATIC_ROOT:
        return open_json(STATIC_ROOT)
    if STATICFILES_DIRS:
        for staticfiles_dir in STATICFILES_DIRS:
            return open_json(staticfiles_dir)


def clean_my_obj(obj):
    if obj and isinstance(obj, (list, tuple, set)):
        return type(obj)(clean_my_obj(x) for x in obj if x)
    elif obj and isinstance(obj, dict):
        return type(obj)(
            (clean_my_obj(k), clean_my_obj(v)) for k, v in obj.items() if k and v)
    else:
        return obj


def phone_number(cleaned_data, field):
        # Le .replace(" ", "") n'est utile que si on garde la contrainte en base max_length=10
        tmp = cleaned_data.get(field)
        if tmp:
            prs = phonenumbers.parse(tmp, "FR")
            cleaned_data[field] = phonenumbers.format_number(
                prs, phonenumbers.PhoneNumberFormat.NATIONAL).replace(" ", "")
        return cleaned_data[field]
