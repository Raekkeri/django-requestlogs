# django-requestlogs

django-requestlogs is a package providing middleware and other helpers for audit logging.

# Installation

Install using `pip`:

    pip install django-requestlogs

Add `'requestlogs.middleware.RequestLogsMiddleware'` to `MIDDLEWARE` settings.

    MIDDLEWARE = [
        ...
        'requestlogs.middleware.RequestLogsMiddleware',
    ]

This will start storing the request logs using the default `STORAGE_CLASS`, which in fact just uses Python logger named `requestlogs`. Now you can, for example, redirect these logs to a file with the following `LOGGING` configuration:

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
