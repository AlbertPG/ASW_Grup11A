import typing

from django.http import HttpRequest
from rest_framework_api_key.models import APIKey
from rest_framework_api_key.permissions import HasAPIKey

from empo_news.errors import UnauthenticatedException


class KeyPermission(HasAPIKey):
    def has_permission(self, request: HttpRequest, view: typing.Any) -> bool:
        key = request.META.get('HTTP_API_KEY', '')

        try:
            api_key = APIKey.objects.get_from_key(key)
        except APIKey.DoesNotExist:
            raise UnauthenticatedException

        return super().has_permission(request, view)
