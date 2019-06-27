from unittest.mock import patch

import django
from django.contrib.auth import get_user_model
from django.test import override_settings, modify_settings
if django.VERSION[0] < 2:
    from django.conf.urls import url
else:
    from django.urls import re_path as url
from rest_framework import serializers
from rest_framework import viewsets
from rest_framework.authentication import BaseAuthentication
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APITestCase
from rest_framework.views import APIView

from requestlogs import get_requestlog_entry
from requestlogs.storages import BaseEntrySerializer


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


@api_view(['GET'])
def api_view_function(request):
    return Response({'status': 'ok'})


urlpatterns = [
    url(r'^/?$', View.as_view()),
    url(r'^user/?$', ProtectedView.as_view()),
    url(r'^set-user-manually/?$', SetUserManually.as_view()),
    url(r'^login/?$', LoginView.as_view()),
    url(r'^viewset/?$', ViewSet.as_view({'get': 'list', 'post': 'create'})),
    url(r'^viewset/1/?$', ViewSet.as_view({'get': 'retrieve'})),
    url(r'^func/?$', api_view_function),
    url(r'^error/?$', ServerErrorView.as_view()),
]


class TestStorage(object):
    serializer_class = BaseEntrySerializer

    def store(self, entry):
        self.do_store(self.serializer_class(entry).data)

    def do_store(self, data):
        # This is to be mocked by tests
        pass



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
            self.expected['request']['data'] = None
            self.assert_stored(mocked_store, self.expected)
