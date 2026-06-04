from django.apps import AppConfig
import os

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """Crea carpetas de media automáticamente al arrancar (necesario en Windows)."""
        from django.conf import settings
        folders = [
            settings.MEDIA_ROOT,
            os.path.join(settings.MEDIA_ROOT, 'photos'),
            os.path.join(settings.MEDIA_ROOT, 'banderas'),
            os.path.join(settings.MEDIA_ROOT, 'equipos'),
            os.path.join(settings.MEDIA_ROOT, 'carrusel'),
            os.path.join(settings.MEDIA_ROOT, 'reglas'),
        ]
        for folder in folders:
            os.makedirs(folder, exist_ok=True)
