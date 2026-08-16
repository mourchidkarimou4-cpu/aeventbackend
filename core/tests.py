import os
from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from .models import AvisClient


class ResetAdminPasswordTestCase(APITestCase):
    def setUp(self):
        self._old_token = os.environ.get('ADMIN_RESET_TOKEN')
        os.environ['ADMIN_RESET_TOKEN'] = 'secret-token'
        self.admin = User.objects.create_superuser('root', 'root@a.com', 'oldpass123')

    def tearDown(self):
        if self._old_token is None:
            os.environ.pop('ADMIN_RESET_TOKEN', None)
        else:
            os.environ['ADMIN_RESET_TOKEN'] = self._old_token

    def test_reset_with_valid_token(self):
        res = self.client.post('/api/core/reset-admin-password/', {
            'token': 'secret-token', 'new_password': 'newpassword123',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password('newpassword123'))

    def test_reset_with_wrong_token(self):
        res = self.client.post('/api/core/reset-admin-password/', {
            'token': 'wrong', 'new_password': 'newpassword123',
        }, format='json')
        self.assertEqual(res.status_code, 403)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password('oldpass123'))

    def test_reset_rejects_short_password(self):
        res = self.client.post('/api/core/reset-admin-password/', {
            'token': 'secret-token', 'new_password': 'short',
        }, format='json')
        self.assertEqual(res.status_code, 400)


class AvisTestCase(APITestCase):
    def test_post_avis_requires_name_and_message(self):
        res = self.client.post('/api/core/avis/', {
            'name': '', 'message': 'Super', 'note': 5,
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_post_avis_rejects_out_of_range_note(self):
        res = self.client.post('/api/core/avis/', {
            'name': 'Aïcha', 'message': 'Super', 'note': 9,
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_post_avis_not_approved_by_default(self):
        res = self.client.post('/api/core/avis/', {
            'name': 'Aïcha', 'message': 'Super', 'note': 5,
        }, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertFalse(AvisClient.objects.get(name='Aïcha').is_approved)
        self.assertEqual(self.client.get('/api/core/avis/').data, [])

    def test_public_avis_only_approved(self):
        AvisClient.objects.create(name='Pub', message='Ok', note=5, is_approved=True)
        AvisClient.objects.create(name='Brouillon', message='Non', note=5, is_approved=False)
        res = self.client.get('/api/core/avis/')
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['name'], 'Pub')


class CookieAuthTestCase(APITestCase):
    """JWT en cookies HttpOnly : login / refresh / logout."""

    def setUp(self):
        self.admin = User.objects.create_user('cook', 'cook@a.com', 'strongpass123')

    def _login(self):
        return self.client.post('/api/auth/token/', {
            'username': 'cook', 'password': 'strongpass123',
        }, format='json')

    def test_login_sets_http_only_cookies_and_authenticates(self):
        res = self._login()
        self.assertEqual(res.status_code, 200)
        self.assertIn('access', self.client.cookies)
        self.assertIn('refresh', self.client.cookies)
        self.assertEqual(self.client.cookies['access']['httponly'], True)

        me = self.client.get('/api/core/auth/me/')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data['username'], 'cook')

    def test_login_rejects_bad_credentials(self):
        res = self.client.post('/api/auth/token/', {
            'username': 'cook', 'password': 'wrong',
        }, format='json')
        self.assertEqual(res.status_code, 401)

    def test_refresh_rotates_tokens_from_cookie(self):
        self._login()
        res = self.client.post('/api/auth/token/refresh/')
        self.assertEqual(res.status_code, 200)
        me = self.client.get('/api/core/auth/me/')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data['username'], 'cook')

    def test_refresh_without_cookie_rejected(self):
        res = self.client.post('/api/auth/token/refresh/')
        self.assertEqual(res.status_code, 401)

    def test_logout_clears_cookies_and_revokes_access(self):
        self._login()
        res = self.client.post('/api/auth/logout/')
        self.assertEqual(res.status_code, 200)
        # Le cookie est expiré (vide) côté client après delete_cookie
        self.assertEqual(self.client.cookies['access'].value, '')
        self.assertEqual(self.client.cookies['refresh'].value, '')
        me = self.client.get('/api/core/auth/me/')
        self.assertEqual(me.status_code, 401)

    def test_expired_or_garbage_cookie_means_anonymous_not_500(self):
        # Un cookie access invalide ne doit ni casser les pages publiques ni renvoyer 500
        self.client.cookies['access'] = 'not-a-jwt'
        res = self.client.get('/api/core/avis/')
        self.assertEqual(res.status_code, 200)
        me = self.client.get('/api/core/auth/me/')
        self.assertEqual(me.status_code, 401)
