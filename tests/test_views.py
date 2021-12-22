import io
import logging
from unittest.mock import patch, Mock

import django
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import override_settings, modify_settings
if django.VERSION[0] < 2:
    from django.conf.urls import url
else:
    from django.urls import re_path as url
from django.views import View as DjangoView
from rest_framework import serializers
from rest_framework import viewsets
from rest_framework.authentication import BaseAuthentication
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APITestCase
from rest_framework.views import APIView

from requestlogs import get_requestlog_entry
from requestlogs.logging import RequestIdContext
from requestlogs.storages import BaseEntrySerializer, BaseRequestSerializer, BaseStorage


class View(APIView):
    requestlogs_action_names = {
        'get': 'get-some-resources',
        'post': 'post-other-stuff',
    }

    def get(self, request):
        return Response(self.get_response_data())

    def post(self, request):
        return Response({'status': 'ok'})

    def get_response_data(self):
        return {}


class ViewSet(viewsets.ViewSet):
    requestlogs_action_names = {
        'list': 'list-stuffs',
        'retrieve': 'obj-detail',
        'create': 'create-object',
    }

    def list(self, request):
        return Response({})

    def retrieve(self, request):
        return Response({})

    def create(self, request):
        return Response({})

    def w_logging(self, request):
        logger = logging.getLogger('request_id_test')
        logger.info('GET with logging ({})'.format(request.GET.get('q')))
        return Response({})


class SimpleAuth(BaseAuthentication):
    def authenticate(self, request):
        if request.META.get('HTTP_AUTHORIZATION') == 'Password 123':
            return get_user_model().objects.get(), ('simple',)


class SetUserManually(APIView):
    def get(self, request):
        get_requestlog_entry(request).user = get_user_model().objects.first()
        return Response({})


class LoginView(APIView):
    def get(self, request):
        from django.contrib.auth import login
        login(request, get_user_model().objects.get())
        return Response({})


class ProtectedView(View):
    authentication_classes = (SimpleAuth,)
    permission_classes = (IsAuthenticated,)


class ServerErrorView(APIView):
    authentication_classes = (SimpleAuth,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        # This will raise an error resulting a response with 500 status code
        {'one': 1}['two']


class BasicDjangoView(DjangoView):
    def get(self, request):
        return HttpResponse('')

    def post(self, request):
        return HttpResponse('')


@api_view(['GET'])
def api_view_function(request):
    return Response({'status': 'ok'})


urlpatterns = [
    url(r'^/?$', View.as_view()),
    url(r'^django/?$', BasicDjangoView.as_view()),
    url(r'^user/?$', ProtectedView.as_view()),
    url(r'^set-user-manually/?$', SetUserManually.as_view()),
    url(r'^login/?$', LoginView.as_view()),
    url(r'^viewset/?$', ViewSet.as_view({'get': 'list', 'post': 'create'})),
    url(r'^viewset/1/?$', ViewSet.as_view({'get': 'retrieve'})),
    url(r'^func/?$', api_view_function),
    url(r'^error/?$', ServerErrorView.as_view()),
    url(r'^logging/?$', ViewSet.as_view({'get': 'w_logging'})),
]


class TestStorage(BaseStorage):
    def store(self, entry):
        self.do_store(self.prepare(entry))

    def do_store(self, data):
        # This is to be mocked by tests
        pass


class RequestHeaderEntry(BaseEntrySerializer):
    class RequestSerializer(BaseRequestSerializer):
        accept_header = serializers.CharField(source='request.META.HTTP_ACCEPT')

    request = RequestSerializer()


class RequestLogsTestMixin(object):
    def assert_stored(self, mocked_store, expected_data):
        stored_data = dict(mocked_store.call_args[0][0])
        assert stored_data.pop('execution_time', None)
        assert stored_data.pop('timestamp', None)
        assert stored_data.pop('ip_address', None)

        for k, v in expected_data.items():
            assert stored_data.pop(k) == v

        assert stored_data == {}


@override_settings(
    ROOT_URLCONF=__name__,
    REQUESTLOGS={'STORAGE_CLASS': 'tests.test_views.TestStorage'},
)
@modify_settings(MIDDLEWARE={
    'append': 'requestlogs.middleware.RequestLogsMiddleware',
})
class TestStoredData(RequestLogsTestMixin, APITestCase):
    def test_get_bare_view(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store:
            response = self.client.get('/?q=a')
            self.assert_stored(mocked_store, {
                'action_name': 'get-some-resources',
                'request': {
                    'method': 'GET',
                    'full_path': '/?q=a',
                    'data': '{}',
                    'query_params': '{"q": "a"}',
                },
                'response': {
                    'status_code': 200,
                    'data': '{}',
                },
                'user': {'id': None, 'username': None},
            })

    def test_post_bare_view(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store:
            response = self.client.post('/', data={'test': 1})
            self.assert_stored(mocked_store, {
                'action_name': 'post-other-stuff',
                'request': {
                    'method': 'POST',
                    'full_path': '/',
                    'data': '{"test": "1"}',
                    'query_params': "{}",
                },
                'response': {
                    'status_code': 200,
                    'data': '{"status": "ok"}',
                },
                'user': {'id': None, 'username': None},
            })

    def test_get_django_view(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store:
            response = self.client.get('/django')
            self.assert_stored(mocked_store, {
                'action_name': None,
                'request': {
                    'method': 'GET',
                    'full_path': '/django',
                    'data': '{}',
                    'query_params': "{}",
                },
                'response': {
                    'status_code': 200,
                    'data': None
                },
                'user': {'id': None, 'username': None},
            })

    def test_post_django_view(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store:
            response = self.client.post('/django', data={'test': 1})
            self.assert_stored(mocked_store, {
                'action_name': None,
                'request': {
                    'method': 'POST',
                    'full_path': '/django',
                    'data': '{"test": "1"}',
                    'query_params': "{}",
                },
                'response': {
                    'status_code': 200,
                    'data': None
                },
                'user': {'id': None, 'username': None},
            })


    def test_api_view(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store:
            response = self.client.get('/func?test=1')
            self.assert_stored(mocked_store, {
                'action_name': None,
                'request': {
                    'method': 'GET',
                    'full_path': '/func?test=1',
                    'data': "{}",
                    'query_params': '{"test": "1"}',
                },
                'response': {
                    'status_code': 200,
                    'data': '{"status": "ok"}',
                },
                'user': {'id': None, 'username': None},
            })

    @override_settings(
        REQUESTLOGS={
            'STORAGE_CLASS': 'tests.test_views.TestStorage',
            'SERIALIZER_CLASS': 'tests.test_views.RequestHeaderEntry',
            'SECRETS': ['passwd']
        },
    )
    def test_store_http_header(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store:
            response = self.client.get('/func?test=1', HTTP_ACCEPT='application/json')
            self.assert_stored(mocked_store, {
                'action_name': None,
                'request': {
                    'method': 'GET',
                    'full_path': '/func?test=1',
                    'data': "{}",
                    'query_params': '{"test": "1"}',
                    'accept_header': 'application/json',
                },
                'response': {
                    'status_code': 200,
                    'data': '{"status": "ok"}',
                },
                'user': {'id': None, 'username': None},
            })


@override_settings(
    ROOT_URLCONF=__name__,
    REQUESTLOGS={'STORAGE_CLASS': 'tests.test_views.TestStorage',
                 'SECRETS': ['passwd']},
)
@modify_settings(MIDDLEWARE={
    'append': 'requestlogs.middleware.RequestLogsMiddleware',
})
class TestDataTypes(APITestCase):
    def test_simple_str_response(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store, \
                patch('tests.test_views.View.get_response_data') as \
                mocked_get_data:
            mocked_get_data.return_value = 'ok'
            response = self.client.get('/')
            assert mocked_store.call_args[0][0]['response']['data'] == '"ok"'


class ActionNameStorage(TestStorage):
    class serializer_class(serializers.Serializer):
        action_name = serializers.CharField()


@override_settings(
    ROOT_URLCONF=__name__,
    REQUESTLOGS={'STORAGE_CLASS': 'tests.test_views.ActionNameStorage',
                 'SECRETS': ['passwd']},
)
@modify_settings(MIDDLEWARE={
    'append': 'requestlogs.middleware.RequestLogsMiddleware',
})
class TestActionNames(APITestCase):
    def test_action_names_with_get_method(self):
        with patch('tests.test_views.ActionNameStorage.do_store') as \
                mocked_store:
            response = self.client.get('/?q=a')
            assert mocked_store.call_args[0][0] == {
                'action_name': 'get-some-resources'}

    def test_viewset_action_name_get_method(self):
        with patch('tests.test_views.ActionNameStorage.do_store') as \
                mocked_store:
            response = self.client.get('/viewset')
            assert mocked_store.call_args[0][0] == {
                'action_name': 'list-stuffs'}

    def test_viewset_action_name_get_method_other_action(self):
        with patch('tests.test_views.ActionNameStorage.do_store') as \
                mocked_store:
            response = self.client.get('/viewset/1')
            assert mocked_store.call_args[0][0] == {
                'action_name': 'obj-detail'}

    def test_viewset_action_name_post_method(self):
        with patch('tests.test_views.ActionNameStorage.do_store') as \
                mocked_store:
            response = self.client.post('/viewset')
            assert mocked_store.call_args[0][0] == {
                'action_name': 'create-object'}


@override_settings(
    ROOT_URLCONF=__name__,
    REQUESTLOGS={'STORAGE_CLASS': 'tests.test_views.TestStorage',
                 'SECRETS': ['passwd']},
)
@modify_settings(MIDDLEWARE={
    'append': 'requestlogs.middleware.RequestLogsMiddleware',
})
class TestRemoveSecrets(APITestCase):
    def test_remove_password_from_request(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store:
            response = self.client.post('/', data={'passwd': 1})
            d = '{"passwd": "***"}'
            assert mocked_store.call_args[0][0]['request']['data'] == d

    def test_remove_password_from_response(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store, \
                patch('tests.test_views.View.get_response_data') as \
                mocked_get_data:
            mocked_get_data.return_value = {'passwd': 'test'}
            response = self.client.get('/')
            d = '{"passwd": "***"}'
            assert mocked_store.call_args[0][0]['response']['data'] == d


class UserStorage(TestStorage):
    class serializer_class(serializers.Serializer):
        class UserSerializer(serializers.Serializer):
            id = serializers.IntegerField()
            username = serializers.CharField()

        user = UserSerializer()


@override_settings(
    ROOT_URLCONF=__name__,
    REQUESTLOGS={'STORAGE_CLASS': 'tests.test_views.UserStorage',
                 'SECRETS': ['passwd']},
)
@modify_settings(MIDDLEWARE={
    'append': 'requestlogs.middleware.RequestLogsMiddleware',
})
class TestAuthenticationAndPermissions(APITestCase):
    def test_authenticated_user(self):
        user = get_user_model().objects.create_user('u1')
        self.client.credentials(HTTP_AUTHORIZATION='Password 123')

        with patch('tests.test_views.UserStorage.do_store') as mocked_store:
            response = self.client.get('/user/')

        assert mocked_store.call_args[0][0] == {
            'user': {'id': user.id, 'username': 'u1'}}
        assert response.status_code == 200

    def test_unautenticated_user(self):
        with patch('tests.test_views.UserStorage.do_store') as mocked_store:
            response = self.client.get('/user/')

        assert response.status_code == 403
        assert mocked_store.call_args[0][0] == {
            'user': {'id': None, 'username': None}}


@override_settings(
    ROOT_URLCONF=__name__,
    REQUESTLOGS={'STORAGE_CLASS': 'tests.test_views.UserStorage'},
)
class TestSetUser(APITestCase):
    @modify_settings(MIDDLEWARE={
        'append': 'requestlogs.middleware.RequestLogsMiddleware',
    })
    def test_set_user_manually(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store:
            user = get_user_model().objects.create_user('u1')
            response = self.client.get('/set-user-manually')
            assert response.status_code == 200

        assert mocked_store.call_args[0][0] == {
            'user': {'id': user.id, 'username': 'u1'}}

    @override_settings(MIDDLEWARE=[
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'requestlogs.middleware.RequestLogsMiddleware',
    ])
    def test_set_user_automatically_on_login(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store:
            user = get_user_model().objects.create_user('u1')
            response = self.client.get('/login')

        assert mocked_store.call_args[0][0] == {
            'user': {'id': user.id, 'username': 'u1'}}


@override_settings(
    ROOT_URLCONF=__name__,
    REQUESTLOGS={'STORAGE_CLASS': 'tests.test_views.TestStorage'},
)
@modify_settings(MIDDLEWARE={
    'append': 'requestlogs.middleware.RequestLogsMiddleware',
})
class TestServerError(RequestLogsTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user('u1')
        self.client.credentials(HTTP_AUTHORIZATION='Password 123')
        self.expected = {
            'action_name': None,
            'request': {
                'method': 'POST',
                'full_path': '/error',
                'query_params': '{}',
            },
            'response': {
                'status_code': 500,
                'data': None,
            },
            'user': {'id': self.user.id, 'username': 'u1'},
        }

    @override_settings(
        REST_FRAMEWORK={
            'EXCEPTION_HANDLER': 'requestlogs.views.exception_handler',
        })
    def test_500_response(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store:
            self.assertRaises(
                KeyError, self.client.post, '/error', {'pay': 'load'})
            self.expected['request']['data'] = '{"pay": "load"}'
            self.assert_stored(mocked_store, self.expected)

    def test_500_response_without_custom_exception_handler(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store:
            self.assertRaises(
                KeyError, self.client.post, '/error', {'pay': 'load'})
            self.expected['request']['data'] = '{"pay": "load"}'
            self.assert_stored(mocked_store, self.expected)


class RequestIdSerializer(serializers.Serializer):
    request_id = serializers.CharField(source='request.request_id')


class LoggingMixin(object):
    def _setup_logging(self):
        log_format = '{levelname} {request_id} {message}'
        stream = io.StringIO('')
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter(log_format, style='{'))
        logger = logging.getLogger('request_id_test')
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.addFilter(RequestIdContext())
        self._log_stream = stream

    def _assert_logged_lines(self, lines):
        self._log_stream.seek(0)
        raw = self._log_stream.read()
        assert raw.endswith('\n')
        logged_lines = [i for i in raw.split('\n')][:-1]
        assert logged_lines == lines


@override_settings(
    ROOT_URLCONF=__name__,
    REQUESTLOGS={
        'STORAGE_CLASS': 'tests.test_views.TestStorage',
        'SERIALIZER_CLASS': 'tests.test_views.RequestIdSerializer',
    },
)
@modify_settings(MIDDLEWARE={
    'append': [
        'requestlogs.middleware.RequestLogsMiddleware',
        'requestlogs.middleware.RequestIdMiddleware',
    ],
})
class TestRequestIdMiddleware(LoggingMixin, RequestLogsTestMixin, APITestCase):
    def test_request_id_generated(self):
        with patch('tests.test_views.TestStorage.do_store') \
                as mocked_store, patch('uuid.uuid4') as mocked_uuid:
            mocked_uuid.side_effect = [Mock(hex='12345dcba')]
            response = self.client.get('/')
            assert mocked_store.call_args[0][0] == {'request_id': '12345dcba'}

    def test_python_logging_with_request_id(self):
        # First build logging setup which outputs entries with request_id.
        # We cannot use `self.assertLogs`, because it uses the default
        # formatter, and so request_id wouldn't be seen in log output.
        self._setup_logging()

        # Now that logging is set up to capture formatted log entries into the
        # `stream`, we can do the request and finally check the logged result.
        with patch('uuid.uuid4') as mocked_uuid:
            mocked_uuid.side_effect = [Mock(hex='12345dcba')]
            self.client.get('/logging?q=yes')

        self._assert_logged_lines(['INFO 12345dcba GET with logging (yes)'])

    def test_python_logging_and_requestlogs_entry(self):
        self._setup_logging()

        with patch('tests.test_views.TestStorage.do_store') \
                as mocked_store, patch('uuid.uuid4') as mocked_uuid, \
                patch('uuid.uuid4') as mocked_uuid:
            mocked_uuid.side_effect = [
                Mock(hex='12345dcba'), Mock(hex='ffc999123')]
            self.client.get('/logging?q=1')
            self.client.get('/logging?q=2')

            call_args1, call_args2 = mocked_store.call_args_list
            assert call_args1[0][0] == {'request_id': '12345dcba'}
            assert call_args2[0][0] == {'request_id': 'ffc999123'}

        self._assert_logged_lines([
            'INFO 12345dcba GET with logging (1)',
            'INFO ffc999123 GET with logging (2)',
        ])

    @override_settings(
        REQUESTLOGS={
            'STORAGE_CLASS': 'tests.test_views.TestStorage',
            'SERIALIZER_CLASS': 'requestlogs.storages.RequestIdEntrySerializer',
        },
    )
    def test_default_request_id_serializer(self):
        self._setup_logging()

        with patch('tests.test_views.TestStorage.do_store') \
                as mocked_store, patch('uuid.uuid4') as mocked_uuid, \
                patch('uuid.uuid4') as mocked_uuid:
            mocked_uuid.side_effect = [Mock(hex='12345dcba')]
            self.client.get('/logging?q=1')
            self.assert_stored(mocked_store, {
                'action_name': None,
                'request': {
                    'method': 'GET',
                    'full_path': '/logging?q=1',
                    'data': '{}',
                    'query_params': '{"q": "1"}',
                    'request_id': '12345dcba',
                },
                'response': {
                    'status_code': 200,
                    'data': '{}',
                },
                'user': {'id': None, 'username': None},
            })

        self._assert_logged_lines(['INFO 12345dcba GET with logging (1)'])


@override_settings(
    ROOT_URLCONF=__name__,
    REQUESTLOGS={
        'STORAGE_CLASS': 'tests.test_views.TestStorage',
        'SERIALIZER_CLASS': 'tests.test_views.RequestIdSerializer',
        'REQUEST_ID_HTTP_HEADER': 'X_DJANGO_REQUEST_ID',
    },
)
@modify_settings(MIDDLEWARE={
    'append': [
        'requestlogs.middleware.RequestLogsMiddleware',
        'requestlogs.middleware.RequestIdMiddleware',
    ],
})
class TestReuseRequestId(LoggingMixin, APITestCase):
    def test_reuse_request_id(self):
        self._setup_logging()

        uuid = '6359abe9f7d849e09a324791c6a6c976'
        self.client.credentials(X_DJANGO_REQUEST_ID=uuid)

        with patch('tests.test_views.TestStorage.do_store') \
                as mocked_store, patch('uuid.uuid4') as mocked_uuid, \
                patch('uuid.uuid4') as mocked_uuid:
            mocked_uuid.side_effect = []
            response = self.client.get('/logging?q=p')
            assert mocked_store.call_args[0][0] == {'request_id': uuid}

        self._assert_logged_lines([
            'INFO 6359abe9f7d849e09a324791c6a6c976 GET with logging (p)'])

    def test_bad_request_id(self):
        self.client.credentials(X_DJANGO_REQUEST_ID='BAD')
        self._test_request_id_generated()

    def test_no_request_id_present(self):
        self._test_request_id_generated()

    def _test_request_id_generated(self):
        with patch('tests.test_views.TestStorage.do_store') \
                as mocked_store, patch('uuid.uuid4') as mocked_uuid, \
                patch('uuid.uuid4') as mocked_uuid:
            mocked_uuid.side_effect = [Mock(hex='12345dcba')]
            response = self.client.get('/')
            assert mocked_store.call_args[0][0] == {'request_id': '12345dcba'}
