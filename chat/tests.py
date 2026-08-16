from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from .models import MessageChat


class ChatApiTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'password123')
        self.session_id = 'sess-test-session-123'

    def test_client_can_post_to_session(self):
        res = self.client.post(
            f'/api/chat/session/?id={self.session_id}',
            {'client_nom': 'Koffi', 'contenu': 'Bonjour !'},
            format='json'
        )
        self.assertEqual(res.status_code, 201)
        self.assertFalse(res.data['is_admin'])

    def test_session_rejects_invalid_id(self):
        res = self.client.post(
            '/api/chat/session/?id=../../etc/passwd',
            {'contenu': 'Bonjour'},
            format='json'
        )
        self.assertEqual(res.status_code, 400)

    def test_session_rejects_empty_message(self):
        res = self.client.post(
            f'/api/chat/session/?id={self.session_id}',
            {'contenu': '   '},
            format='json'
        )
        self.assertEqual(res.status_code, 400)

    def test_admin_reply_marks_admin(self):
        MessageChat.objects.create(
            session_id=self.session_id, client_nom='Client',
            contenu='Question', is_admin=False,
        )
        self.client.force_authenticate(self.admin)
        res = self.client.post(
            '/api/chat/reply/',
            {'session_id': self.session_id, 'contenu': 'Réponse'},
            format='json'
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data['is_admin'])

    def test_sessions_aggregates_unread(self):
        MessageChat.objects.create(
            session_id=self.session_id, client_nom='Client',
            contenu='Question', is_admin=False,
        )
        self.client.force_authenticate(self.admin)
        res = self.client.get('/api/chat/sessions/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data[0]['session_id'], self.session_id)
        self.assertEqual(res.data[0]['unread'], 1)
        self.assertEqual(res.data[0]['client_nom'], 'Client')
