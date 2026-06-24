from django.db import models
from django.utils.text import slugify


class Article(models.Model):
    CATEGORIES = [
        ('actualite',  'Actualité'),
        ('recette',    'Recette & Tutoriel'),
        ('evenement',  'Événement'),
        ('conseil',    'Conseil & Astuce'),
    ]
    title       = models.CharField(max_length=200, verbose_name="Titre")
    slug        = models.SlugField(max_length=200, unique=True, blank=True)
    category    = models.CharField(max_length=20, choices=CATEGORIES, default='actualite')
    excerpt     = models.TextField(verbose_name="Résumé", blank=True)
    content     = models.TextField(verbose_name="Contenu")
    image       = models.ImageField(upload_to='blog/', null=True, blank=True)
    is_published = models.BooleanField(default=False)
    views       = models.PositiveIntegerField(default=0)
    order       = models.PositiveIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Article"
        verbose_name_plural = "Articles"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
