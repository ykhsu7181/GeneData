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


class ExternalContentThrottle(DataAccessRateThrottle):
    scope = "external_content"


class ExternalManifestThrottle(DataAccessRateThrottle):
    scope = "external_manifest"


class ExternalSequenceThrottle(DataAccessRateThrottle):
    scope = "external_sequence"


class ExternalBatchThrottle(DataAccessRateThrottle):
    scope = "external_batch"
