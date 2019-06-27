# django-requestlogs

django-requestlogs is a package providing middleware and other helpers for audit logging.

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
  - django-requestlogs internally attaches the entry object to the Django request object, and uses this attribute name. Override if it causes collusions.
