from fuocore.excs import ProviderIOError


class XiamiIOError(ProviderIOError):
    def __init__(self, message=''):
        super().__init__(message, provider='xiami')
