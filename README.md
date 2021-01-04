# django-requestlogs

[![Build Status](https://travis-ci.org/Raekkeri/django-requestlogs.svg?branch=master)](https://travis-ci.org/Raekkeri/django-requestlogs)
![PyPI](https://img.shields.io/pypi/v/django-requestlogs.svg)

django-requestlogs is a package providing middleware and other helpers for audit logging.
The middleware collects information about request-response cycle into log entries. The
collected information can be fully customized, but the out-of-the-box implementation
includes

- user ID and username
- request (path, method, payload..)
- response (status code, payload..)
- general information, such as timestamp, execution time

Finally the log entry is stored in predefined storage, which by default is configurable
using Django's logging system.

Once installed, log storage should start showing entries such as the following:

```
{'action_name': None, 'execution_time': '00:00:00.024900', 'timestamp': '2019-07-01T07:05:34.217703Z', 'ip_address': None, 'request': OrderedDict([('method', 'GET'), ('full_path', '/'), ('data', '{}'), ('query_params', '{}')]), 'response': OrderedDict([('status_code', 200), ('data', '{"ok": true}')]), 'user': OrderedDict([('id', 1), ('username', 'admin')])}
```

*Note that to get IP address logged as well, the optional dependency `django-ipware` must be installed.*

## Motivation

django-requestlogs attempts to provide tools for implementing audit logging (audit trail)
to systems that require such feature. These systems typically must have the ability to
tell "what information the end-user has accessed (and what information was sent to the
system)?". django-requestlogs hooks into the Django REST framework in the simplest
way possible while logging every request without the need of remembering to enable it
for each view separately.

Currently django-requestlogs package is primarily focusing on working seamlessly with
Django REST framework. While plain Django requests are also collected, storing their request
and response payloads is not fully supported.

# Requirements

- Django (1.11, 2.0, 2.1, 2.2, 3.0)
- Django REST framework

Optional dependencies:

- django-ipware
  - if installed, this is used for storing end-user's IP address

# Installation

Install using `pip`:

    pip install django-requestlogs

Add `'requestlogs.middleware.RequestLogsMiddleware'` to `MIDDLEWARE` settings.

```python
MIDDLEWARE = [
    ...
    'requestlogs.middleware.RequestLogsMiddleware',
]
```

Set `'requestlogs.views.exception_handler'` as rest_framework's exception handler
(this will make sure requestlog entry has all possible data available about the
request in case of a 500 error):

```python
REST_FRAMEWORK={
    ...
    'EXCEPTION_HANDLER': 'requestlogs.views.exception_handler',
}
```

The middleware is now ready to start storing requestlog entries using the default
`STORAGE_CLASS`, which in fact just uses Python logger named `requestlogs`. Now you can,
for example, redirect these logs to a file with the following `LOGGING` configuration:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'requestlogs_to_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/tmp/requestlogs.log',
        },
    },
    'loggers': {
        'requestlogs': {
            'handlers': ['requestlogs_to_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

# Settings

Requestlogs can be customized using Django settings. The following shows the default values for the available settings:

```python
REQUESTLOGS = {
    'STORAGE_CLASS': 'requestlogs.storages.LoggingStorage',
    'ENTRY_CLASS': 'requestlogs.entries.RequestLogEntry',
    'SERIALIZER_CLASS': 'requestlogs.storages.BaseEntrySerializer',
    'SECRETS': ['password', 'token'],
    'ATTRIBUTE_NAME': '_requestlog',
    'METHODS': ('GET', 'PUT', 'PATCH', 'POST', 'DELETE'),
}
```

- **STORAGE_CLASS**
  - Path to the Python class which will handle storing the log entries. Override this if you only need to reimplement the storage mechanism. This may be the case e.g. when choosing what data to store.
- **ENTRY_CLASS**
  - Path to the Python class which handles the construction of the complete requestlogs entry. Override this for full customization of the requestlog entry behaviour.
- **SERIALIZER_CLASS**
  - Path to the serializer class which is used to serialize the requestlog entry before storage. By default this is a subclass of `rest_framework.serializers.Serializer`.
- **SECRETS**
  - List of keys in request/response data which will be replaced with `'***'` in the stored entry.
- **ATTRIBUTE_NAME**
  - django-requestlogs internally attaches the entry object to the Django request object, and uses this attribute name. Override if it causes collisions.
- **METHODS**
  - django-requestlogs will handle only HTTP methods defined by this setting. By default it handles all HTTP methods.


# Logging with Request ID

django-requestlogs also contains a middleware and logging helpers to associate a
request-specific identifier (uuid) to logging messages. This aims to help
distinguishing messages to certain request-response cycle, which can be useful
in an application that receives a high number of requests.

The request id is added to the standard logging messages (Django application logs)
by specifying a custom formatter and using the provided logging filter.
The request id can be stored to requestlog entries as well.
The middleware to enable the request id logging does not require the core requestlogs
middleware to be installed.

Under the hood the request id is implemented with help of `threading.local()`.

## Installation

The feature is enabled by adding `requestlogs.middleware.RequestIdMiddleware`
to the `MIDDLEWARE` setting:

```python
MIDDLEWARE = [
    ...
    'requestlogs.middleware.RequestLogsMiddleware',
    'requestlogs.middleware.RequestIdMiddleware',
]
```

Once installed, the application logs should start showing messages with a format such as
the following:

```
2019-07-18 11:56:07,261 INFO 954fb004fb404751a2fa33326101442c urls:31 Handling GET request
2019-07-18 11:56:07,262 DEBUG 954fb004fb404751a2fa33326101442c urls:32 No parameters given
2019-07-18 11:56:07,262 INFO 954fb004fb404751a2fa33326101442c urls:33 All good
```

To add the request id to requestlog entries as well, you can use the provided serializer
class as a starting point:

```python
REQUESTLOGS = {
    ...
    'SERIALIZER_CLASS': 'requestlogs.storages.RequestIdEntrySerializer',
}
```

## Configuration

The middleware has some additional configuration possiblities:


```python
REQUESTLOGS = {
    ...
    'REQUEST_ID_HTTP_HEADER': 'X_DJANGO_REQUEST_ID',
    'REQUEST_ID_ATTRIBUTE_NAME': 'request_id',
}
```
- **REQUEST_ID_HTTP_HEADER**
  - If set, the value of this request header is used as request id (instead of it being
    randomly generated). This must be a valid uuid. One use case for this feature is in
    microservice architecture, where a micreservice calls another, internal microservice.
    Having the log messages of both applications to be formatted with same request id
    might be the preferred outcome.
- **REQUEST_ID_ATTRIBUTE_NAME**
  - The attribute name which is used internally to attach request id to
    `threading.locals()`. Override if it causes collisions.

To add the request id to logging messages of your Django application, use the provided
logging filter and include `request_id` to the log formatter.
Here is the complete logging configuration:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'requestlogs_to_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/tmp/requestlogs.log',
        },
        'root': {
            'class': 'logging.StreamHandler',
            'filters': ['request_id_context'],
            'formatter': 'verbose',
        },
    },
    'loggers': {
        '': {
            'handlers': ['root'],
            'level': 'DEBUG',
        },
        'requestlogs': {
            'handlers': ['requestlogs_to_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'filters': {
        'request_id_context': {
            '()': 'requestlogs.logging.RequestIdContext',
        },
    },
    'formatters': {
        'verbose': {
            'format': '%(asctime)s %(levelname)s %(request_id)s %(module)s:%(lineno)s %(message)s'
        },
    },
}
```
