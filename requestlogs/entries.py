import datetime
import time

from django.utils import timezone

from .base import SETTINGS
from .utils import remove_secrets, get_client_ip


class RequestHandler(object):
    def __init__(self, request):
        self.request = request

    @property
    def method(self):
        return self.request.method

    @property
    def data(self):
        return None

    @property
    def query_params(self):
        return remove_secrets(self.request.GET)

    @property
    def full_path(self):
        return self.request.get_full_path()


class DRFRequestHandler(RequestHandler):
    @property
    def data(self):
        return remove_secrets(self.request.data)

    @property
    def query_params(self):
        return self.request.query_params


class ResponseHandler(object):
    def __init__(self, response):
        self.response = response

    @property
    def status_code(self):
        return self.response.status_code

    @property
    def data(self):
        if hasattr(self.response, 'data'):
            return remove_secrets(self.response.data)
        return {}


class RequestLogEntry(object):
    """The default requestlog entry class"""

    django_request_handler = RequestHandler
    drf_request_handler = DRFRequestHandler
    response_handler = ResponseHandler

    # Private attributes to hold some context
    _user = None

    def __init__(self, request, view_class):
        self.django_request = request
        self.view_class = view_class
        self._initialized_at = time.time()

    def finalize(self, response):
        # Choose request handler
        try:
            drf_request = getattr(response, 'renderer_context', {})['request']
            self.request = self.drf_request_handler(drf_request)
        except KeyError:
            self.request = self.django_request_handler(self.django_request)

        self.response = self.response_handler(response)
        self.store()

    def store(self):
        storage = SETTINGS['STORAGE_CLASS']()
        storage.store(self)

    @property
    def user(self):
        ret = {
            'id': None,
            'username': None,
        }

        user = self._user or getattr(self.django_request, 'user', None)
        if user and user.is_authenticated:
            ret['id'] = user.id
            ret['username'] = user.username

        return ret

    @user.setter
    def user(self, user):
        self._user = user

    @property
    def ip_address(self):
        return get_client_ip(self.django_request)

    @property
    def timestamp(self):
        return timezone.now()

    @property
    def execution_time(self):
        return datetime.timedelta(seconds=time.time() - self._initialized_at)
