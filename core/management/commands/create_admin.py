from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os
import secrets
import string


class Command(BaseCommand):
    help = 'Crée le superuser admin si il nexiste pas'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        email = os.environ.get('ADMIN_EMAIL', 'admin@ams.bj')
        username = os.environ.get('ADMIN_USERNAME', 'admin')
        password = os.environ.get('ADMIN_INITIAL_PASSWORD')

        if User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
            self.stdout.write('Superuser existe déjà.')
            return

        if not password:
            alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
            password = ''.join(secrets.choice(alphabet) for _ in range(24))

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f'Superuser créé : {email}'))
        if not os.environ.get('ADMIN_INITIAL_PASSWORD'):
            self.stdout.write(self.style.WARNING(
                f'Mot de passe temporaire (à changer immédiatement) : {password}'
            ))
