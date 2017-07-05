from django.utils.deprecation import MiddlewareMixin
from threading import current_thread


_requests = {}


def get_current_user():
    t = current_thread()
    if t not in _requests:
        return None
    return _requests[t].user


class RequestMiddleware(MiddlewareMixin):
    def process_request(self, request):
        _requests[current_thread()] = request
