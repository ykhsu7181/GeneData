from rest_framework.throttling import SimpleRateThrottle

from files.models import DataAccessToken


class DataAccessRateThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        if isinstance(request.auth, DataAccessToken):
            identity = f"token:{request.auth.token_prefix}"
        else:
            identity = f"ip:{self.get_ident(request)}"
        return self.cache_format % {"scope": self.scope, "ident": identity}


class ExternalMetadataThrottle(DataAccessRateThrottle):
    scope = "external_metadata"


class ExternalAnonymousContentThrottle(DataAccessRateThrottle):
    scope = "external_anonymous_content"

    def get_cache_key(self, request, view):
        if isinstance(request.auth, DataAccessToken):
            return None
        return super().get_cache_key(request, view)


class ExternalAnonymousContentDailyThrottle(ExternalAnonymousContentThrottle):
    scope = "external_anonymous_content_daily"


class ExternalAuthenticatedContentThrottle(DataAccessRateThrottle):
    scope = "external_authenticated_content"

    def get_cache_key(self, request, view):
        if not isinstance(request.auth, DataAccessToken):
            return None
        return super().get_cache_key(request, view)


class ExternalManifestThrottle(DataAccessRateThrottle):
    scope = "external_manifest"


class ExternalSequenceThrottle(DataAccessRateThrottle):
    scope = "external_sequence"


class ExternalBatchThrottle(DataAccessRateThrottle):
    scope = "external_batch"
