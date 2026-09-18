"""
Custom Authentication classes for Cookie and Bearer JWT authentication.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed


class CookieJWTAuthentication(JWTAuthentication):
    """
    Extends SimpleJWT's JWTAuthentication to read tokens from:
    1. HTTP Authorization header: 'Bearer <token>'
    2. HTTP-only Cookie: 'access_token'
    """

    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            # Fallback to reading access_token from cookies
            raw_token = request.COOKIES.get("access_token")
            if raw_token is None:
                return None
        else:
            raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None

        try:
            validated_token = self.get_validated_token(raw_token)
            return self.get_user(validated_token), validated_token
        except (InvalidToken, AuthenticationFailed):
            if header is not None:
                raise
            return None
