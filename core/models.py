from django.db import models


class SiteSettings(models.Model):
    whatsapp_number = models.CharField(max_length=20, default='+22900000000')
    whatsapp_message_default = models.TextField(default="Bonjour A'Events Bénin, je souhaite avoir des informations.")
    address = models.TextField(default="Cotonou, Bénin")
    email_contact = models.EmailField(blank=True, default='contact@aevents-benin.com')
    instagram_url = models.URLField(blank=True)
    facebook_url  = models.URLField(blank=True)
    tiktok_url    = models.URLField(blank=True)
    tagline = models.CharField(max_length=200, default="Prestige. Qualité. Émotion.")
    hero_subtitle = models.TextField(default="Chaque détail compte. Chaque événement est unique.")
    momo_number = models.CharField(max_length=20, blank=True)
    momo_name = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Paramètres du site"
        verbose_name_plural = "Paramètres du site"

    def __str__(self):
        return "Paramètres A'Events Bénin"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class GaleriePhoto(models.Model):
    CATEGORIES = [
        ('patisserie', 'Pâtisserie'),
        ('traiteur',   'Traiteur'),
        ('imprimerie', 'Imprimerie'),
        ('academy',    'Academy'),
        ('coffret',    'Coffret'),
    ]
    title    = models.CharField(max_length=200, verbose_name="Titre")
    category = models.CharField(max_length=50, choices=CATEGORIES, default='patisserie')
    image    = models.ImageField(upload_to='galerie/', verbose_name="Photo")
    order    = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Photo galerie"
        verbose_name_plural = "Photos galerie"
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"{self.title} ({self.category})"


class Newsletter(models.Model):
    email      = models.EmailField(unique=True, verbose_name="Email")
    name       = models.CharField(max_length=100, blank=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Abonné newsletter"
        verbose_name_plural = "Abonnés newsletter"

    def __str__(self):
        return self.email


class AvisClient(models.Model):
    name       = models.CharField(max_length=100, verbose_name="Nom")
    email      = models.EmailField(blank=True)
    note       = models.PositiveSmallIntegerField(default=5, choices=[(i, i) for i in range(1, 6)])
    message    = models.TextField(verbose_name="Avis")
    service    = models.CharField(max_length=50, choices=[
        ('patisserie', 'Pâtisserie'),
        ('traiteur',   'Traiteur'),
        ('imprimerie', 'Imprimerie'),
        ('academy',    'Academy'),
        ('general',    'Général'),
    ], default='general')
    is_approved = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Avis client"
        verbose_name_plural = "Avis clients"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.note}/5"
