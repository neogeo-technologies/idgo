# Copyright (c) 2017-2019 Datasud.
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


from base64 import b64decode
from django.contrib.auth import authenticate
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.http.multipartparser import MultiPartParser
from django.http.multipartparser import MultiPartParserError
from functools import wraps
from io import BytesIO


# def pagination_handler(f):
#     _x = 1
#     _y = 10
#
#     def clean(value, default: int):
#         try:
#             value = int(value)
#         except ValueError:
#             return default
#         else:
#             return value > 0 and value or default
#
#     @wraps(f)
#     def wrapper(*args, **kwargs):
#         x = clean(kwargs.pop('page_number', ''), _x)
#         y = clean(kwargs.pop('page_size', ''), _y)
#         i = (x * y) - y
#         j = i + y
#         kwargs.update({'i': i, 'j': j})
#         return f(*args, **kwargs)
#     return wrapper


class BasicAuth(object):

    def view_or_basicauth(self, view, request, test_func, *args, **kwargs):
        http_auth = request.META.get('HTTP_AUTHORIZATION', '')
        if http_auth not in ('', None):
            auth = http_auth.split()
            if len(auth) == 2:
                if auth[0].lower() == 'basic':
                    try:
                        username, password = b64decode(
                            auth[1]).decode('utf-8').split(':')
                    except Exception:
                        pass
                    user = authenticate(username=username, password=password)
                    if user is not None and user.is_active:
                        request.user = user
                        return view(*args, **kwargs)
        return HttpResponse(status=401)

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            request = None
            args = list(args)
            for arg in args:
                if isinstance(arg, WSGIRequest):
                    request = arg
                    break
            return self.view_or_basicauth(
                f, request, lambda u: u.is_authenticated(), *args, **kwargs)
        return wrapper


def parse_request(request):
    if hasattr(request, '_body'):
        data = BytesIO(request._body)
    else:
        data = request
    try:
        return request.parse_file_upload(request.META, data)
    except MultiPartParserError:
        request._mark_post_parse_error()
        raise
