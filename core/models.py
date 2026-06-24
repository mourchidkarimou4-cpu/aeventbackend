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
    image    = models.URLField(verbose_name="Photo", blank=True, null=True)
    order    = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Photo galerie"
        verbose_name_plural = "Photos galerie"
        ordering = ['order', '-created_at']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

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

    def save(self, *args, **kwargs):
        # Note: AvisClient n'a pas de champ 'photo', cette méthode était boguée
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} — {self.note}/5" 


class Temoignage(models.Model):
    name     = models.CharField(max_length=100, verbose_name="Nom du client")
    role     = models.CharField(max_length=200, blank=True, verbose_name="Rôle / Occasion")
    message  = models.TextField(verbose_name="Témoignage", help_text="Le message du client")  # ← AJOUTÉ
    photo    = models.ImageField(upload_to='temoignages/', null=True, blank=True, verbose_name="Photo / Capture")
    note     = models.PositiveSmallIntegerField(default=5, choices=[(i, i) for i in range(1, 6)])
    is_active = models.BooleanField(default=True)
    order    = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Témoignage"
        verbose_name_plural = "Témoignages"
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"{self.name} — {self.note}/5"


def compress_image(image_field, max_size=(800, 800), quality=85):
    """Compresse une image uploadée."""
    from PIL import Image
    import io
    from django.core.files.uploadedfile import InMemoryUploadedFile
    import sys

    if not image_field:
        return image_field

    img = Image.open(image_field)

    # Convertir en RGB si nécessaire
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    # Redimensionner si trop grande
    img.thumbnail(max_size, Image.LANCZOS)

    # Sauvegarder en mémoire
    output = io.BytesIO()
    img.save(output, format='WEBP', quality=quality, optimize=True)
    output.seek(0)

    return InMemoryUploadedFile(
        output, 'ImageField',
        f"{image_field.name.rsplit('.', 1)[0]}.webp",
        'image/webp',
        sys.getsizeof(output),
        None
    )


class AdminProfile(models.Model):
    ROLES = [
        ('super_admin', 'Super Administrateur'),
        ('manager',     'Manager'),
        ('editor',      'Éditeur'),
        ('viewer',      'Lecteur'),
    ]
    user        = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='admin_profile')
    role        = models.CharField(max_length=20, choices=ROLES, default='viewer')
    phone       = models.CharField(max_length=20, blank=True)
    avatar_url  = models.URLField(blank=True)
    permissions = models.JSONField(default=dict)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Profil admin"
        verbose_name_plural = "Profils admin"

    def __str__(self):
        return f"{self.user.username} — {self.role}"
