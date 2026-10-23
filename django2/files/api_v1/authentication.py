from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from files.models import DataAccessToken


class DataAccessTokenAuthentication(BaseAuthentication):
    """Authenticate ``Authorization: Bearer gdt_...`` without a Django login."""

    keyword = b"bearer"

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts:
            return None
        if parts[0].lower() != self.keyword or len(parts) != 2:
            raise AuthenticationFailed({
                "detail": "Use one Bearer API token.",
                "code": "invalid_authorization",
            })
        try:
            raw_token = parts[1].decode("ascii")
        except UnicodeDecodeError as exc:
            raise AuthenticationFailed({
                "detail": "Invalid API token.",
                "code": "invalid_token",
            }) from exc
        token = DataAccessToken.authenticate(raw_token)
        if token is None:
            raise AuthenticationFailed({
                "detail": "Invalid or expired API token.",
                "code": "invalid_token",
            })
        now = timezone.now()
        DataAccessToken.objects.filter(pk=token.pk).update(last_used_at=now)
        token.last_used_at = now
        return AnonymousUser(), token

    def authenticate_header(self, request):
        return "Bearer"
