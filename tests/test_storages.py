import django
from django.urls import reverse_lazy
from django.test import override_settings, TestCase
if django.VERSION[0] < 2:
    from django.conf.urls import url
else:
    from django.urls import re_path as url
from rest_framework import serializers

from requestlogs.storages import JsonDumpField, BaseStorage


urlpatterns = [
    url(r'^/?$', lambda r: None, name='home'),
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
