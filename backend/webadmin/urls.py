from django.urls import path

from . import pwa, views

urlpatterns = [
    path("manifest.webmanifest", pwa.manifest_view, name="webadmin-pwa-manifest"),
    path("service-worker.js", pwa.service_worker_view, name="webadmin-pwa-service-worker"),
    path(
        "map-tiles/<int:z>/<int:x>/<int:y>.png",
        views.map_tile_proxy_view,
        name="webadmin-map-tiles",
    ),
    path("login/", views.login_view, name="webadmin-login"),
    path("logout/", views.logout_view, name="webadmin-logout"),
    path("", views.dashboard_view, name="webadmin-dashboard"),
    path("sites/", views.sites_list_view, name="webadmin-sites"),
    path("sites/<int:pk>/", views.site_detail_view, name="webadmin-site-detail"),
    path("sites/<int:pk>/modifier/", views.site_edit_view, name="webadmin-site-edit"),
    path("sites/<int:pk>/supprimer/", views.site_delete_view, name="webadmin-site-delete"),
    path("vigiles/", views.vigiles_list_view, name="webadmin-vigiles"),
    path("controllers/", views.controllers_list_view, name="webadmin-controllers"),
    path("controllers/<int:pk>/", views.controller_detail_view, name="webadmin-controller-detail"),
    path(
        "controllers/<int:pk>/supprimer/",
        views.controller_delete_view,
        name="webadmin-controller-delete",
    ),
    path("vigiles/<int:pk>/", views.vigile_detail_view, name="webadmin-vigile-detail"),
    path("vigiles/<int:pk>/cv.pdf", views.vigile_cv_pdf_view, name="webadmin-vigile-cv-pdf"),
    path("vigiles/<int:pk>/supprimer/", views.vigile_delete_view, name="webadmin-vigile-delete"),
    path("affectations/", views.affectations_list_view, name="webadmin-affectations"),
    path(
        "affectations/titulaires/",
        views.affectations_titulaires_view,
        name="webadmin-affectations-titulaires",
    ),
    path(
        "affectations/titulaires/reintegrer/<int:fixed_post_id>/",
        views.reinstate_titular_view,
        name="webadmin-reinstate-titular",
    ),
    path(
        "affectations/titulaires/retirer/<int:fixed_post_id>/",
        views.retire_titular_view,
        name="webadmin-retire-titular",
    ),
    path(
        "affectations/titulaires/liberer-suspendu/<int:fixed_post_id>/",
        views.dismiss_suspended_titular_view,
        name="webadmin-dismiss-suspended-titular",
    ),
    path("affectations/<int:pk>/modifier/", views.affectation_edit_view, name="webadmin-affectation-edit"),
    path(
        "affectations/<int:pk>/supprimer/",
        views.affectation_delete_view,
        name="webadmin-affectation-delete",
    ),
    path("alertes/", views.alertes_view, name="webadmin-alertes"),
    path("alertes/status.json", views.critical_alerts_status_view, name="webadmin-critical-alerts-status"),
    path("rapports/", views.rapports_view, name="webadmin-rapports"),
    path("rapports/export/csv/", views.export_reports_csv_view, name="webadmin-rapports-export-csv"),
    path("pointages/", views.pointages_view, name="webadmin-pointages"),
    path("pointages/export/csv/", views.export_pointages_csv_view, name="webadmin-pointages-export-csv"),
    path("notifications-push/", views.notifications_push_view, name="webadmin-notifications-push"),
    path("alerts/<int:alert_id>/acquitter/", views.ack_alert_view, name="webadmin-ack-alert"),
    path(
        "affectations/<int:pk>/acquitter-retard/",
        views.ack_replacement_assignment_view,
        name="webadmin-ack-replacement",
    ),
    path("dispatch/", views.dispatch_view, name="webadmin-dispatch"),
]
