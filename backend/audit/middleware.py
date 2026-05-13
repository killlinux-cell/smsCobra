from .models import AuditLog


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated and request.path.startswith("/api/"):
            AuditLog.objects.create(
                user=request.user,
                action=f"{request.method} {request.path}",
                metadata={},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:255],
            )
        return response
