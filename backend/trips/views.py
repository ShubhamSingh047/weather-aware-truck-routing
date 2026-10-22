import logging

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .providers.errors import ProviderError
from .providers.geocoding import search_places
from .serializers import TripPlanSerializer
from .services import plan_trip

logger = logging.getLogger(__name__)


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
def geocode(request):
    try:
        return Response({"results": search_places(request.query_params.get("q", ""))})
    except ProviderError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(["POST"])
def plan(request):
    serializer = TripPlanSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        result = plan_trip(serializer.to_trip_request())
    except ProviderError as exc:
        logger.warning("trip planning failed: %s", exc)
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    return Response(result)
