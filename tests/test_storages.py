from io import BytesIO
from unittest.mock import patch

import django
from django.urls import reverse_lazy
from django.test import override_settings, modify_settings, TestCase
if django.VERSION[0] < 2:
    from django.conf.urls import url
else:
    from django.urls import re_path as url
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.test import APITestCase

from requestlogs.storages import JsonDumpField, BaseStorage


@api_view(['POST'])
def upload_view(request):
    class FileSerializer(serializers.Serializer):
        file = serializers.FileField()

    s = FileSerializer(data=request.data)
    assert s.is_valid()
    return Response({'status': 'ok'})


urlpatterns = [
    url(r'^/?$', lambda r: None, name='home'),
    url(r'^upload/?$', upload_view),
]


class SimpleStorage(BaseStorage):
    class serializer_class(serializers.Serializer):
        blob = JsonDumpField()


@override_settings(ROOT_URLCONF=__name__)
class TestSerializeProxyObject(TestCase):
    def test_serialize_proxy(self):
        storage = SimpleStorage()
        s = storage.prepare({'blob': {'url': reverse_lazy('home')}})
        assert s == {'blob': '{"url": "/"}'}


@override_settings(
    ROOT_URLCONF=__name__,
    REQUESTLOGS={'STORAGE_CLASS': 'tests.test_views.TestStorage'},
)
@modify_settings(MIDDLEWARE={
    'append': 'requestlogs.middleware.RequestLogsMiddleware',
})
class TestWithFileUpload(APITestCase):
    def test_post_file(self):
        buf = BytesIO(b'\x89PNG')
        with patch('tests.test_views.TestStorage.do_store') as mocked_store:
            response = self.client.post('/upload', data={'file': buf})

        assert mocked_store.call_args[0][0]['request']['data'] == \
            '{"file": "<InMemoryUploadedFile, size=4>"}'
