from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from .models import Article


class ArticleApiTestCase(APITestCase):
    def setUp(self):
        self.published = Article.objects.create(
            title="Article publié", category='actualite',
            excerpt="Excerpt", content="Contenu", is_published=True,
        )
        self.draft = Article.objects.create(
            title="Article brouillon", category='conseil',
            content="Contenu brouillon", is_published=False,
        )

    def test_anonymous_only_sees_published(self):
        res = self.client.get('/api/blog/')
        self.assertEqual(res.status_code, 200)
        ids = [a['id'] for a in res.data['results']]
        self.assertIn(self.published.id, ids)
        self.assertNotIn(self.draft.id, ids)

    def test_admin_sees_drafts(self):
        admin = User.objects.create_superuser('admin', 'a@a.com', 'password123')
        self.client.force_authenticate(admin)
        res = self.client.get('/api/blog/')
        ids = [a['id'] for a in res.data['results']]
        self.assertIn(self.draft.id, ids)

    def test_slugs_are_unique_on_collision(self):
        first = Article.objects.create(title="Titre dupliqué", content="x", is_published=True)
        second = Article.objects.create(title="Titre dupliqué", content="y", is_published=True)
        self.assertNotEqual(first.slug, second.slug)

    def test_retrieve_increments_views_atomically(self):
        res = self.client.get(f"/api/blog/{self.published.slug}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['views'], 1)
        self.published.refresh_from_db()
        self.assertEqual(self.published.views, 1)
