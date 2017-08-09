from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponseServerError
from django.shortcuts import render
from functools import wraps


class GenericException(Exception):
    def __init__(self, *args):
        self.args = args

    def __str__(self):
        return str(self.args)


class CriticalException(GenericException):
    def __init__(self, *args):
        super().__init__(*args)


class CKANSyncingError(GenericException):
    def __init__(self, *args):
        super().__init__(*args)


class ExceptionsHandler(object):

    template_html_500 = 'idgo_admin/servererror.html'

    def __init__(self, ignore=None):
        self.ignore = ignore or []

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
                if self.is_ignored(e):
                    return f(*args, **kwargs)
                print('[Server Error] ->', e.__str__())
                if request:
                    return render(
                        self.request, self.template_html_500, status=500)
                return HttpResponseServerError()

        return wrapper

    def is_ignored(self, exception):
        return type(exception) in self.ignore
