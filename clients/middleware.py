"""Language middleware for French/English bilingual support."""
from django.utils import translation
from django.conf import settings


class LanguageMiddleware:
    """Detect and set user language preference from cookie, query param, or header."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = self._get_language(request)
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()

        response = self.get_response(request)
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            language,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            samesite=settings.LANGUAGE_COOKIE_SAMESITE,
        )
        return response

    def _get_language(self, request):
        # 1. Query parameter override
        lang = request.GET.get('lang')
        if lang and lang in dict(settings.LANGUAGES):
            return lang

        # 2. Cookie
        lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if lang and lang in dict(settings.LANGUAGES):
            return lang

        # 3. Browser Accept-Language header
        accept = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        if 'fr' in accept.lower()[:5]:
            return 'fr'

        # 4. Default
        return settings.LANGUAGE_CODE[:2]
