from django.shortcuts import render
from django.urls import reverse
from functools import wraps
import os
import requests
import string
from urllib.parse import urlparse
from uuid import uuid4


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


def download(url, media_root, **params):
    for i in range(0, 10):  # Try at least ten times before raise
        try:
            r = requests.get(url, params=params, stream=True)
        except Exception as e:
            error = e
            continue
        else:
            break
    else:
        raise error
    r.raise_for_status()

    filename = \
        os.path.join(create_dir(media_root), urlparse(url).path.split('/')[-1])

    # TODO(@m431m) -> https://github.com/django/django/blob/3c447b108ac70757001171f7a4791f493880bf5b/docs/topics/files.txt#L120

    with open(filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)

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
