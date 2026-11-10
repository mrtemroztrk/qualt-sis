from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.http import require_safe


@require_safe
def campus_index(request):
    """Serve the team's interface from the same origin as its API."""
    try:
        page = settings.FRONTEND_INDEX_PATH.open("rb")
    except FileNotFoundError:
        raise Http404("The campus interface is unavailable.")
    return FileResponse(page, content_type="text/html; charset=utf-8")
