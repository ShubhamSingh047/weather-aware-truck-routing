from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .services import TripRequest

# Weather is fetched for 1 past day + 6 forecast days. Leaving room for a long
# drive plus the 48 h heatmap window caps how far ahead a trip can start.
MAX_DAYS_AHEAD = 3
MAX_HOURS_IN_PAST = 2


class PointSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)
    label = serializers.CharField(required=False, allow_blank=True, max_length=200)


class TripPlanSerializer(serializers.Serializer):
    origin = PointSerializer()
    destination = PointSerializer()
    departure = serializers.DateTimeField()
    load_lbs = serializers.FloatField(min_value=0, max_value=80_000)
    interval_miles = serializers.ChoiceField(choices=[10, 25, 50], default=25)
    demo_storm = serializers.BooleanField(default=False)

    def validate_departure(self, value):
        now = timezone.now()
        if value < now - timedelta(hours=MAX_HOURS_IN_PAST):
            raise serializers.ValidationError("Departure can't be in the past.")
        if value > now + timedelta(days=MAX_DAYS_AHEAD):
            raise serializers.ValidationError(
                f"Departure must be within {MAX_DAYS_AHEAD} days; forecasts beyond that aren't reliable."
            )
        return value

    def validate(self, attrs):
        o, d = attrs["origin"], attrs["destination"]
        if abs(o["lat"] - d["lat"]) < 1e-3 and abs(o["lon"] - d["lon"]) < 1e-3:
            raise serializers.ValidationError("Origin and destination are the same place.")
        return attrs

    def to_trip_request(self) -> TripRequest:
        data = self.validated_data
        return TripRequest(
            origin=(data["origin"]["lat"], data["origin"]["lon"]),
            destination=(data["destination"]["lat"], data["destination"]["lon"]),
            departure_ts=data["departure"].timestamp(),
            load_lbs=data["load_lbs"],
            interval_miles=int(data["interval_miles"]),
            demo_storm=data["demo_storm"],
        )
