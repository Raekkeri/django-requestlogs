from . import get_requestlog_entry


class RequestLogsMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # DRF sets the `cls` attribute
        if getattr(view_func, 'cls', None):
            get_requestlog_entry(request=request, view_class=view_func.cls)

    def __call__(self, request):
        response = self.get_response(request)
        get_requestlog_entry(request).finalize(response)
        return response
