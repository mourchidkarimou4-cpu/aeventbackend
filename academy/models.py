from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db.models import Count, Case, When, IntegerField
from decimal import Decimal


class FormationManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()

    def with_stats(self):
        return self.get_queryset().annotate(
            confirmed_count=Count(
                Case(
                    When(reservations__status__in=['confirmed', 'paid'], then=1),
                    output_field=IntegerField()
                )
            )
        )

class Formation(models.Model):
    objects = FormationManager()
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

    # ─────────────────────────────────────────────────────────────
    # MÉTHODES (utiliser annotate en queryset pour éviter N+1)
    # ─────────────────────────────────────────────────────────────
    
    def get_confirmed_count(self):
        """Compte les réservations confirmées/payées (utilisé par properties)."""
        return self.reservations.filter(
            status__in=['confirmed', 'paid']
        ).count()

    @property
    def available_seats(self):
        """Nombre de places disponibles en temps réel.
        
        ⚠️ N+1 QUERY ISSUE: Cette property cause une requête par formation.
        Préférer: annotate(confirmed_count=...) dans le queryset
        """
        confirmed = self.get_confirmed_count()
        return max(0, self.total_seats - confirmed)

    @property
    def is_full(self):
        return self.available_seats == 0

    @property
    def fill_percentage(self):
        if self.total_seats == 0:
            return 100
        confirmed = self.get_confirmed_count()
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


import cloudinary.models as cld

class FormationPresentielle(models.Model):
    DOMAINE_CHOICES = [
        ('patisserie', 'Pâtisserie'),
        ('cuisine', 'Cuisine'),
        ('traiteur', 'Traiteur'),
        ('imprimerie', 'Imprimerie'),
        ('autre', 'Autre'),
    ]
    titre           = models.CharField(max_length=300)
    edition         = models.CharField(max_length=100, blank=True)
    domaine         = models.CharField(max_length=50, choices=DOMAINE_CHOICES, default='patisserie')
    description     = models.TextField(blank=True)
    affiche         = cld.CloudinaryField('affiche', folder='ams/formations', blank=True, null=True)
    est_gratuite    = models.BooleanField(default=True)
    prix            = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    has_bourses     = models.BooleanField(default=False)
    nb_bourses      = models.PositiveIntegerField(null=True, blank=True)
    age_min         = models.PositiveIntegerField(null=True, blank=True)
    age_max         = models.PositiveIntegerField(null=True, blank=True)
    nb_places       = models.PositiveIntegerField(null=True, blank=True)
    duree           = models.CharField(max_length=100, blank=True)
    est_pratique    = models.BooleanField(default=True)
    parrain         = models.CharField(max_length=300, blank=True)
    sites           = models.JSONField(default=list, blank=True)
    date_debut_inscription = models.DateField(null=True, blank=True)
    date_fin_inscription   = models.DateField(null=True, blank=True)
    date_tirage     = models.DateField(null=True, blank=True)
    date_lancement  = models.DateField(null=True, blank=True)
    date_fin        = models.DateField(null=True, blank=True)
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Formation présentielle'
        verbose_name_plural = 'Formations présentielles'

    def __str__(self):
        return f"{self.titre} — {self.edition}" if self.edition else self.titre

    @property
    def inscription_ouverte(self):
        from django.utils import timezone
        today = timezone.now().date()
        if self.date_debut_inscription and self.date_fin_inscription:
            return self.date_debut_inscription <= today <= self.date_fin_inscription
        return False


class DossierCandidature(models.Model):
    STATUT_CHOICES = [
        ('soumis', 'Soumis'),
        ('en_etude', 'En étude'),
        ('retenu', 'Retenu'),
        ('rejete', 'Rejeté'),
    ]
    formation       = models.ForeignKey(FormationPresentielle, on_delete=models.CASCADE, related_name='dossiers')
    nom_complet     = models.CharField(max_length=200)
    email           = models.EmailField(blank=True)
    telephone       = models.CharField(max_length=20)
    date_naissance  = models.DateField(null=True, blank=True)
    lettre_motivation = models.TextField(blank=True)
    piece_identite  = cld.CloudinaryField('piece_identite', folder='ams/dossiers', blank=True, null=True)
    photo_identite  = cld.CloudinaryField('photo_identite', folder='ams/dossiers', blank=True, null=True)
    statut          = models.CharField(max_length=20, choices=STATUT_CHOICES, default='soumis')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Dossier de candidature'
        verbose_name_plural = 'Dossiers de candidature'

    def __str__(self):
        return f"{self.nom_complet} — {self.formation.titre}"
