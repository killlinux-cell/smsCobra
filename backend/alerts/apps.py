from django.apps import AppConfig


class AlertsConfig(AppConfig):
    name = "alerts"

    def ready(self):
        from .firebase_init import init_firebase

        init_firebase()
