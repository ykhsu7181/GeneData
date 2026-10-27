class GeneDataError(Exception):
    exit_code = 1


class InputError(GeneDataError):
    exit_code = 2


class ApiError(GeneDataError):
    exit_code = 3

    def __init__(self, message, *, status=None, code=None):
        super().__init__(message)
        self.status = status
        self.code = code


class NetworkError(GeneDataError):
    exit_code = 4


class SnapshotMismatchError(GeneDataError):
    exit_code = 5


class DownloadError(GeneDataError):
    exit_code = 6
