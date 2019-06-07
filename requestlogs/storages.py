import json
import logging

from rest_framework import serializers


logger = logging.getLogger('requestlogs')


class JsonDumpField(serializers.Field):
    def to_representation(self, value):
        return json.dumps(value)


class BaseEntrySerializer(serializers.Serializer):
    class RequestSerializer(serializers.Serializer):
        method = serializers.CharField(read_only=True)
        full_path = serializers.CharField(read_only=True)
        data = JsonDumpField(read_only=True)
        query_params = JsonDumpField(read_only=True)

    class ResponseSerializer(serializers.Serializer):
        status_code = serializers.IntegerField(read_only=True)
        data = JsonDumpField(read_only=True)

    execution_time = serializers.DurationField(read_only=True)
    timestamp = serializers.DateTimeField(read_only=True)
    ip_address = serializers.CharField(read_only=True)
    request = RequestSerializer(read_only=True)
    response = ResponseSerializer(read_only=True)


class LoggingStorage(object):
    serializer_class = BaseEntrySerializer

    def store(self, entry):
        logger.info(self.prepare(entry))

    def prepare(self, entry):
        return self.serializer_class(entry).data
