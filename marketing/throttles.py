"""Custom DRF throttles for marketing APIs."""
from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


class BurstRateThrottle(SimpleRateThrottle):
    scope = 'burst'

    def get_cache_key(self, request, view):  # type: ignore[override]
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return None
        return self.cache_format % {'scope': self.scope, 'ident': str(user.pk)}


class CampaignSendRateThrottle(SimpleRateThrottle):
    scope = 'campaign_send'

    def get_cache_key(self, request, view):  # type: ignore[override]
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return None
        return self.cache_format % {'scope': self.scope, 'ident': str(user.pk)}
