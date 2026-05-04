from django.db import models
from django.core.exceptions import ValidationError
import os


def validate_print_file(file):
    """Valide que le fichier uploadé est sécurisé et du bon type."""
    allowed_extensions = ['.pdf', '.png', '.jpg', '.jpeg']
    max_size_mb = 50

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(
            f"Format non autorisé : {ext}. Formats acceptés : PDF, PNG, JPG."
        )
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(
            f"Fichier trop volumineux ({file.size // (1024*1024)} Mo). Maximum : {max_size_mb} Mo."
        )


def print_file_upload_path(instance, filename):
    """Chemin d'upload sécurisé avec UUID pour éviter les conflits et l'énumération."""
    import uuid
    ext = os.path.splitext(filename)[1].lower()
    safe_name = f"{uuid.uuid4().hex}{ext}"
    return f"imprimerie/{instance.created_at.strftime('%Y/%m') if instance.created_at else 'uploads'}/{safe_name}"


class QuoteRequest(models.Model):
    """Demande de devis — Traiteur OU Imprimerie."""

    class ServiceType(models.TextChoices):
        TRAITEUR   = 'traiteur',   'Traiteur / Réception'
        IMPRIMERIE = 'imprimerie', 'Imprimerie'
        BOTH       = 'both',       'Traiteur + Imprimerie'

    class Status(models.TextChoices):
        NEW       = 'new',       'Nouveau'
        REVIEWING = 'reviewing', 'En cours d\'étude'
        QUOTED    = 'quoted',    'Devis envoyé'
        ACCEPTED  = 'accepted',  'Devis accepté'
        REJECTED  = 'rejected',  'Refusé'
        COMPLETED = 'completed', 'Réalisé'

    # Client
    customer_name     = models.CharField(max_length=200, verbose_name="Nom complet")
    customer_whatsapp = models.CharField(max_length=20, verbose_name="WhatsApp")
    customer_email    = models.EmailField(blank=True)

    # Type de service
    service_type = models.CharField(
        max_length=20, choices=ServiceType.choices,
        verbose_name="Type de service"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEW
    )

    # Événement
    event_date        = models.DateField(null=True, blank=True, verbose_name="Date de l'événement")
    event_location    = models.CharField(max_length=300, blank=True, verbose_name="Lieu")
    event_description = models.TextField(blank=True, verbose_name="Description de l'événement")

    # Traiteur : détails dynamiques stockés en JSON
    # Structure attendue :
    # {
    #   "guests_count": 150,
    #   "menu_type": "cocktail | dîner assis | buffet",
    #   "equipment": {
    #     "tables": 15, "chaises": 150, "couverts": true,
    #     "nappes": true, "verrerie": true, "sono": false
    #   },
    #   "service_staff": true,
    #   "budget_estimate": 500000,
    #   "dietary_notes": "Plats halal requis"
    # }
    catering_details = models.JSONField(
        default=dict, blank=True,
        verbose_name="Détails traiteur (JSON)",
        help_text="Nombre de convives, matériel, type de menu..."
    )

    # Imprimerie : détails
    # {
    #   "print_type": "cartes | flyers | banderoles | menus | kakemonos",
    #   "quantity": 500,
    #   "format": "A4 | A5 | personnalisé",
    #   "finish": "brillant | mat | pelliculage",
    #   "notes": "..."
    # }
    print_details = models.JSONField(
        default=dict, blank=True,
        verbose_name="Détails imprimerie (JSON)"
    )

    # Note générale
    additional_note = models.TextField(blank=True, verbose_name="Note complémentaire")

    # Devis réponse (rempli par le gérant)
    quote_amount  = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    quote_message = models.TextField(blank=True, verbose_name="Message du devis envoyé")
    quote_sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Demande de devis"
        verbose_name_plural = "Demandes de devis"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_service_type_display()}] {self.customer_name} — {self.created_at.strftime('%d/%m/%Y') if self.created_at else ''}"


class PrintFile(models.Model):
    """Fichier uploadé dans le cadre d'une demande d'imprimerie."""
    quote_request = models.ForeignKey(
        QuoteRequest, on_delete=models.CASCADE,
        related_name='print_files',
        null=True, blank=True,
        help_text="Demande de devis associée (optionnel à la création)"
    )
    file = models.FileField(
        upload_to=print_file_upload_path,
        validators=[validate_print_file],
        verbose_name="Fichier (PDF / PNG / JPG)"
    )
    original_filename = models.CharField(max_length=255, blank=True)
    file_size_kb      = models.PositiveIntegerField(default=0)
    description       = models.CharField(max_length=300, blank=True, verbose_name="Description du fichier")
    uploaded_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fichier imprimerie"
        verbose_name_plural = "Fichiers imprimerie"
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.original_filename} ({self.file_size_kb} Ko)"

    def save(self, *args, **kwargs):
        if self.file and not self.original_filename:
            self.original_filename = self.file.name
        if self.file and not self.file_size_kb:
            self.file_size_kb = self.file.size // 1024
        super().save(*args, **kwargs)
