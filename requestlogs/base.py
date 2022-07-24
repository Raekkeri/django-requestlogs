from django.conf import settings
from django.utils.module_loading import import_string
from django.test.signals import setting_changed


DEFAULT_SETTINGS = {
    'ATTRIBUTE_NAME': '_requestlog',
    'ENTRY_CLASS': 'requestlogs.entries.RequestLogEntry',
    'STORAGE_CLASS': 'requestlogs.storages.LoggingStorage',
    'SERIALIZER_CLASS': 'requestlogs.storages.BaseEntrySerializer',
    'SECRETS': ['password', 'password1', 'password2', 'token', 'HTTP_AUTHORIZATION'],
    'REQUEST_ID_ATTRIBUTE_NAME': 'request_id',
    'REQUEST_ID_HTTP_HEADER': None,
    'METHODS': ('GET', 'PUT', 'PATCH', 'POST', 'DELETE'),
    'JSON_ENSURE_ASCII': True,
    'IGNORE_USER_FIELD': None,
    'IGNORE_USERS': [],
    'IGNORE_PATHS': None,
}


def populate_settings(_settings):
    for k, v in DEFAULT_SETTINGS.items():
        _settings[k] = v
    for k, v in getattr(settings, 'REQUESTLOGS', {}).items():
        _settings[k] = v
    _settings['ENTRY_CLASS'] = import_string(_settings['ENTRY_CLASS'])
    _settings['STORAGE_CLASS'] = import_string(_settings['STORAGE_CLASS'])
    _settings['SERIALIZER_CLASS'] = import_string(
        _settings['SERIALIZER_CLASS'])

    ignore_paths = _settings['IGNORE_PATHS']
    if callable(ignore_paths):
        _settings['IGNORE_PATHS'] = ignore_paths
    elif isinstance(ignore_paths, (tuple, list)):
        _settings['IGNORE_PATHS'] = IgnorePaths(ignore_paths)
    elif isinstance(ignore_paths, str):
        _settings['IGNORE_PATHS'] = import_string(ignore_paths)
    elif ignore_paths:
        raise NotImplementedError('Such `IGNORE_PATHS` not supported')


SETTINGS = {}
populate_settings(SETTINGS)


def get_requestlog_entry(request=None, view_func=None):
    try:
        entry = getattr(request, SETTINGS['ATTRIBUTE_NAME'])
        # `existing` should be something else than `None`
        assert entry
        return entry
    except AttributeError:
        pass

    entry = SETTINGS['ENTRY_CLASS'](request, view_func)
    setattr(request, SETTINGS['ATTRIBUTE_NAME'], entry)
    return entry


def reload_settings(*args, **kwargs):
    setting = kwargs['setting']
    if setting == 'REQUESTLOGS':
        global SETTINGS
        SETTINGS.clear()
        populate_settings(SETTINGS)


setting_changed.connect(reload_settings)


### Utils:

class IgnorePaths(object):
    def __init__(self, paths):
        try:
            from re import Pattern
        except ImportError:
            # Python 3.6 `Pattern`:
            from typing.re import Pattern

        re_paths = set(p for p in paths if isinstance(p, Pattern))
        paths = set(paths) - re_paths

        leading_wildcards = set(p for p in paths if p.startswith('*'))
        trailing_wildcards = set(p for p in paths if p.endswith('*'))
        exacts = paths - leading_wildcards - trailing_wildcards

        self.li = [s.__eq__ for s in exacts]
        self.li.extend([lambda p: p.endswith(s[1:]) for s in leading_wildcards])
        self.li.extend([lambda p: p.startswith(s[:-1]) for s in trailing_wildcards])
        self.li.extend([s.match for s in re_paths])

    def __call__(self, path):
        return any(f(path) for f in self.li)
