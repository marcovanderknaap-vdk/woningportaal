from django.apps import AppConfig


class AanbodConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aanbod"

    def ready(self):
        from . import signals  # noqa: F401
