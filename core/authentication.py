"""Authentification JWT lue depuis un cookie HttpOnly (simplejwt 5.5.1).

simplejwt >= 5.x n'intègre plus le support cookie natif : on l'implémente ici.
Le token d'accès est lu dans le cookie HttpOnly `access` ; l'en-tête
Authorization reste accepté en repli (tests, scripts, clients tiers).
"""
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class CookieJWTAuthentication(JWTAuthentication):

    def get_raw_token_from_cookie(self, request):
        cookie_name = settings.JWT_ACCESS_COOKIE
        if cookie_name and cookie_name in request.COOKIES:
            return request.COOKIES[cookie_name].encode()
        return None

    def authenticate(self, request):
        raw_token = None
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
        else:
            raw_token = self.get_raw_token_from_cookie(request)

        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
        except (InvalidToken, TokenError):
            # Cookie expiré / invalide : requête anonyme plutôt qu'erreur 401.
            # Une page publique ne doit jamais être cassée par un token périmé
            # laissé par le navigateur.
            return None

        return self.get_user(validated_token), validated_token
