from unittest.mock import patch

import django
from django.contrib.auth import get_user_model
from django.test import override_settings, modify_settings
if django.VERSION[0] < 2:
    from django.conf.urls import url
else:
    from django.urls import re_path as url
from rest_framework import serializers
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APITestCase
from rest_framework.views import APIView

from requestlogs import get_requestlog_entry
from requestlogs.storages import BaseEntrySerializer


class View(APIView):
    def get(self, request):
        return Response(self.get_response_data())

    def post(self, request):
        return Response({'status': 'ok'})

    def get_response_data(self):
        return {}


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


urlpatterns = [
    url(r'^/?$', View.as_view()),
    url(r'^user/?$', ProtectedView.as_view()),
    url(r'^set-user-manually/?$', SetUserManually.as_view()),
    url(r'^login/?$', LoginView.as_view()),
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
class Test(RequestLogsTestMixin, APITestCase):
    def test_get_bare_view(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store:
            response = self.client.get('/?q=a')
            self.assert_stored(mocked_store, {
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
            })

    def test_post_bare_view(self):
        with patch('tests.test_views.TestStorage.do_store') as mocked_store:
            response = self.client.post('/', data={'test': 1})
            self.assert_stored(mocked_store, {
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
            })


@override_settings(
    ROOT_URLCONF=__name__,
    REQUESTLOGS={'STORAGE_CLASS': 'tests.test_views.TestStorage',
                 'SECRETS': ['passwd']},
)
@modify_settings(MIDDLEWARE={
    'append': 'requestlogs.middleware.RequestLogsMiddleware',
})
class TestRemoveSecrets(RequestLogsTestMixin, APITestCase):
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
class TestAuthenticationAndPermissions(RequestLogsTestMixin, APITestCase):
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
