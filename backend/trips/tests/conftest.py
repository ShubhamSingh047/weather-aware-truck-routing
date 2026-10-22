import pytest


@pytest.fixture(autouse=True)
def isolated_cache(settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
