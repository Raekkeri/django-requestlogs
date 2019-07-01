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

## Motivation

django-requestlogs attempts to provide tools for implementing audit logging (audit trail)
to systems that require such feature. These systems typically must have the ability to
tell "what information the end-user has accessed (and what information was sent to the
system)?". django-requestlogs hooks into the Django REST framework in the simplest
way possible while logging every request without the need of remembering to enable it
for each view separately.

Currently django-requestlogs package is primarily focusing on working seamlessly with
Django REST framework. While plain Django requests are also collected, their request and
response payload, for example, is not stored.

# Requirements

- Django (1.11, 2.0, 2.1, 2.2)
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

This will start storing the request logs using the default `STORAGE_CLASS`, which in fact just uses Python logger named `requestlogs`. Now you can, for example, redirect these logs to a file with the following `LOGGING` configuration:

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
    'SECRETS': ['password', 'token'],
    'ATTRIBUTE_NAME': '_requestlog',
}
```

- **STORAGE_CLASS**
  - Path to the Python class which will handle storing the log entries. Override this if you only need to reimplement the storage mechanism. This may be the case e.g. when choosing what data to store.
- **ENTRY_CLASS**
  - Path to the Python class which handles the construction of the complete requestlogs entry. Override this for full customization of the requestlog entry behaviour.
- **SECRETS**
  - List of keys in request/response data which will be replaced with `'***'` in the stored entry.
- **ATTRIBUTE_NAME**
  - django-requestlogs internally attaches the entry object to the Django request object, and uses this attribute name. Override if it causes collisions.
