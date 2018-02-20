# Copyright (c) 2017-2018 Datasud.
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


from django.core.handlers.wsgi import WSGIRequest
from django.http import Http404
from functools import wraps


class ProfileHttp404(Http404):
    pass


class GenericException(Exception):
    def __init__(self, *args, **kwargs):
        self.args = args
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __str__(self):
        return str(self.args)


class CriticalException(GenericException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class ConflictError(GenericException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class FakeError(GenericException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class SizeLimitExceededError(GenericException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class ErrorOnDeleteAccount(Exception):
    pass


class ExceptionsHandler(object):

    template_html_500 = 'idgo_admin/servererror.html'

    MESSAGES = {
        'CkanTimeoutError': 'Impossible de joindre le serveur CKAN.'}

    def __init__(self, ignore=None, actions=None):
        self.ignore = ignore or []
        self.actions = actions or {}

    def __call__(self, f):

        @wraps(f)
        def wrapper(*args, **kwargs):
            request = None
            args = list(args)
            for arg in args:
                if isinstance(arg, WSGIRequest):
                    request = arg
            try:
                return f(*args, **kwargs)
            except Exception as e:
                for exception, callback in self.actions.items():
                    if isinstance(e, exception):
                        return callback()

                if self.is_ignored(e):
                    return f(*args, **kwargs)
                raise e
                # qualname = e.__class__.__qualname__
                # context = {
                #     'message': self.MESSAGES.get(qualname)}
                #
                # if request:
                #     return render(request, self.template_html_500,
                #                   context=context, status=500)
                # return HttpResponseServerError()

        return wrapper

    def is_ignored(self, exception):
        return type(exception) in self.ignore
