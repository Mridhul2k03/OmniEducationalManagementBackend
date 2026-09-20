"""
Custom Authentication classes for Cookie and Bearer JWT authentication.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed


class CookieJWTAuthentication(JWTAuthentication):
    """
    Extends SimpleJWT's JWTAuthentication to read tokens seamlessly from:
    1. HTTP Authorization header: 'Bearer <token>'
    2. HTTP-only Cookie: 'access_token'
    """

    def authenticate(self, request):
        header = self.get_header(request)
        raw_token = None

        if header is not None:
            raw_token = self.get_raw_token(header)

        # Fallback to reading access_token from cookies
        if raw_token is None:
            raw_token = request.COOKIES.get("access_token")

        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
            if hasattr(request, "_request") and request._request is not None:
                request._request.user = user
            return user, validated_token
        except (InvalidToken, AuthenticationFailed):
            # If header failed, attempt fallback to cookie
            if header is not None and "access_token" in request.COOKIES:
                cookie_token = request.COOKIES.get("access_token")
                try:
                    validated_token = self.get_validated_token(cookie_token)
                    user = self.get_user(validated_token)
                    if hasattr(request, "_request") and request._request is not None:
                        request._request.user = user
                    return user, validated_token
                except (InvalidToken, AuthenticationFailed):
                    pass
            return None
