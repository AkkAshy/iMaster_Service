from django.apps import AppConfig


class UniversityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'university'

    def ready(self):
        import university.signals  # Замените на актуальное имя приложения и сигналов