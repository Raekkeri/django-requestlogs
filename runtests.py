import sys

import pytest
from django.conf import settings


def run_tests():
    if not settings.configured:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:'
            }
        }
        settings.configure(
            DATABASES=DATABASES,
            REST_FRAMEWORK = {
                'DEFAULT_RENDERER_CLASSES': (
                    'rest_framework.renderers.JSONRenderer',
                    'rest_framework.renderers.BrowsableAPIRenderer',
                ),
            },
            INSTALLED_APPS=(
                'django.contrib.contenttypes',
                'django.contrib.auth',
                'django.contrib.sites',
            ),
            MIDDLEWARE=[],
        )

    return pytest.main()


if __name__ == '__main__':
    sys.exit(run_tests())
