from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal


class Formation(models.Model):
    class Status(models.TextChoices):
        DRAFT     = 'draft',     'Brouillon'
        PUBLISHED = 'published', 'Publiée'
        FULL      = 'full',      'Complète'
        CANCELLED = 'cancelled', 'Annulée'
        PAST      = 'past',      'Passée'

    class Level(models.TextChoices):
        BEGINNER     = 'beginner',     'Débutant'
        INTERMEDIATE = 'intermediate', 'Intermédiaire'
        ADVANCED     = 'advanced',     'Avancé'
        ALL          = 'all',          'Tous niveaux'

    title       = models.CharField(max_length=200, verbose_name="Titre de la formation")
    slug        = models.SlugField(unique=True)
    description = models.TextField(verbose_name="Description complète")
    short_desc  = models.CharField(max_length=300, blank=True, verbose_name="Accroche courte")
    image       = models.ImageField(upload_to='academy/', blank=True, null=True)

    # Programme
    program_details = models.JSONField(
        default=list, blank=True,
        help_text="[{titre, description}, ...] — programme détaillé"
    )
    what_you_learn = models.JSONField(
        default=list, blank=True,
        help_text="Liste de compétences acquises"
    )
    prerequisites = models.TextField(blank=True, verbose_name="Prérequis")

    # Logistique
    instructor_name = models.CharField(max_length=150, blank=True, verbose_name="Formateur")
    level           = models.CharField(max_length=20, choices=Level.choices, default=Level.ALL)
    location        = models.CharField(
        max_length=300, default="Cotonou, Bénin",
        verbose_name="Lieu de la formation"
    )
    is_online = models.BooleanField(default=False, verbose_name="Formation en ligne")

    # Planification
    start_datetime = models.DateTimeField(verbose_name="Date et heure de début")
    end_datetime   = models.DateTimeField(verbose_name="Date et heure de fin")
    duration_label = models.CharField(
        max_length=100, blank=True,
        help_text="Ex: '2 jours', '6 heures' — libellé affiché"
    )

    # Places
    total_seats     = models.PositiveIntegerField(verbose_name="Nombre de places total")
    reserved_seats  = models.PositiveIntegerField(default=0, verbose_name="Places réservées")

    # Tarif
    price = models.DecimalField(
        max_digits=10, decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="Prix (FCFA)"
    )
    early_bird_price = models.DecimalField(
        max_digits=10, decimal_places=0,
        null=True, blank=True,
        verbose_name="Prix Early Bird (FCFA)"
    )
    early_bird_deadline = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Fin du tarif Early Bird"
    )

    status     = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False, verbose_name="Mise en avant")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Formation"
        verbose_name_plural = "Formations"
        ordering = ['start_datetime']

    def __str__(self):
        return f"{self.title} — {self.start_datetime.strftime('%d/%m/%Y')}"

    @property
    def available_seats(self):
        """Nombre de places disponibles en temps réel."""
        confirmed = self.reservations.filter(
            status__in=['confirmed', 'paid']
        ).count()
        return max(0, self.total_seats - confirmed)

    @property
    def is_full(self):
        return self.available_seats == 0

    @property
    def fill_percentage(self):
        if self.total_seats == 0:
            return 100
        confirmed = self.reservations.filter(status__in=['confirmed', 'paid']).count()
        return int((confirmed / self.total_seats) * 100)

    @property
    def current_price(self):
        """Retourne le prix Early Bird si applicable, sinon le prix normal."""
        now = timezone.now()
        if (self.early_bird_price and self.early_bird_deadline
                and now < self.early_bird_deadline):
            return self.early_bird_price
        return self.price

    @property
    def countdown_seconds(self):
        """Secondes restantes avant la formation (pour le décompte frontend)."""
        now = timezone.now()
        if self.start_datetime > now:
            return int((self.start_datetime - now).total_seconds())
        return 0


class Reservation(models.Model):
    class Status(models.TextChoices):
        PENDING   = 'pending',   'En attente de paiement'
        CONFIRMED = 'confirmed', 'Confirmée'
        PAID      = 'paid',      'Payée'
        CANCELLED = 'cancelled', 'Annulée'
        WAITLIST  = 'waitlist',  'Liste d\'attente'

    formation = models.ForeignKey(
        Formation, on_delete=models.PROTECT,
        related_name='reservations'
    )

    # Participant
    participant_name      = models.CharField(max_length=200, verbose_name="Nom complet")
    participant_whatsapp  = models.CharField(max_length=20, verbose_name="WhatsApp")
    participant_email     = models.EmailField(blank=True)
    participant_note      = models.TextField(blank=True, verbose_name="Message / Question")

    # Paiement
    status          = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    amount_paid     = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    payment_method  = models.CharField(
        max_length=50, blank=True,
        help_text="Ex: MTN MoMo, Moov Money, Espèces"
    )
    payment_ref     = models.CharField(max_length=100, blank=True, verbose_name="Référence paiement")
    payment_date    = models.DateTimeField(null=True, blank=True)

    # Référence de réservation
    reference = models.CharField(max_length=20, unique=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"
        ordering = ['-created_at']
        # Un participant ne peut réserver qu'une seule fois la même formation
        unique_together = [['formation', 'participant_whatsapp']]

    def __str__(self):
        return f"{self.participant_name} → {self.formation.title} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.reference:
            import random, string
            self.reference = 'AC' + ''.join(random.choices(string.digits, k=6))
        super().save(*args, **kwargs)
