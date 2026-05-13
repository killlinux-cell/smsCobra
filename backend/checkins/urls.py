from django.urls import path
from .views import (
    BiometricChallengeView,
    BiometricVerifyView,
    EndCheckinView,
    PresenceCheckinView,
    StartCheckinView,
)

urlpatterns = [
    path("biometric/challenge", BiometricChallengeView.as_view(), name="biometric-challenge"),
    path("biometric/verify", BiometricVerifyView.as_view(), name="biometric-verify"),
    path("start", StartCheckinView.as_view(), name="checkin-start"),
    path("end", EndCheckinView.as_view(), name="checkin-end"),
    path("presence", PresenceCheckinView.as_view(), name="checkin-presence"),
]
