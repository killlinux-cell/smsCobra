from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.views import ControllerFaceCheckinView, VigileFaceIdentifyView, VigileFaceLoginView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("dashboard/", include("webadmin.urls")),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/auth/login", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/face-login", VigileFaceLoginView.as_view(), name="vigile_face_login"),
    path("api/v1/auth/face-identify", VigileFaceIdentifyView.as_view(), name="vigile_face_identify"),
    path(
        "api/v1/auth/controller-face-checkin",
        ControllerFaceCheckinView.as_view(),
        name="controller_face_checkin",
    ),
    path("api/v1/auth/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/assignments/", include("shifts.urls")),
    path("api/v1/checkins/", include("checkins.urls")),
    path("api/v1/admin/alerts/", include("alerts.urls")),
    path("api/v1/admin/reports/", include("reports.urls")),
    path("api/v1/admin/sites/", include("sites.urls")),
    path("api/v1/admin/vigiles/", include("accounts.urls_admin")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
