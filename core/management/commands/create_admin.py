from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Crée le superuser admin si il nexiste pas'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        email = 'admin@ams.bj'
        password = 'AMS@admin2026!'
        if not User.objects.filter(email=email).exists():
            User.objects.create_superuser(username='admin', email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f'Superuser créé : {email}'))
        else:
            self.stdout.write('Superuser existe déjà.')
