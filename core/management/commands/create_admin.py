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

        user = User.objects.filter(username=username).first() or User.objects.filter(email=email).first()

        if user:
            if password:
                user.email = email
                user.set_password(password)
                user.save(update_fields=['email', 'password'])
                self.stdout.write(self.style.SUCCESS(f'Mot de passe réinitialisé : {username} / {email}'))
            else:
                self.stdout.write('Superuser existe déjà (ADMIN_INITIAL_PASSWORD non défini).')
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
