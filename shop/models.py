from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nom")
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0, help_text="Ordre d'affichage")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Addon(models.Model):
    """Accompagnement / option supplémentaire associable à plusieurs produits."""
    name = models.CharField(max_length=150, verbose_name="Nom de l'accompagnement")
    price = models.DecimalField(
        max_digits=10, decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="Prix (FCFA)"
    )
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Accompagnement"
        verbose_name_plural = "Accompagnements"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (+{self.price} FCFA)"


class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT,
        related_name='products', verbose_name="Catégorie"
    )
    name = models.CharField(max_length=200, verbose_name="Nom du produit")
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=10, decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="Prix de base (FCFA)"
    )
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    image_gallery = models.JSONField(
        default=list, blank=True,
        help_text="Liste d'URLs d'images supplémentaires"
    )

    # Box / Coffret
    is_box = models.BooleanField(
        default=False,
        verbose_name="Est un coffret/Box",
        help_text="Les coffrets ont des règles d'affichage et de composition spéciales"
    )
    box_contents = models.TextField(
        blank=True,
        help_text="Description du contenu du coffret (affiché client)"
    )
    min_quantity = models.PositiveIntegerField(
        default=1,
        help_text="Quantité minimale de commande"
    )

    # Logistique
    preparation_time_hours = models.PositiveIntegerField(
        default=24,
        verbose_name="Délai de préparation (heures)",
        help_text="Utilisé pour calculer la date de retrait minimum"
    )
    available_addons = models.ManyToManyField(
        Addon,
        blank=True,
        related_name='products',
        verbose_name="Accompagnements disponibles"
    )

    # Disponibilité
    is_available = models.BooleanField(default=True, verbose_name="Disponible")
    is_featured = models.BooleanField(default=False, verbose_name="Mis en avant")
    stock = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Laisser vide = stock illimité"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        ordering = ['-is_featured', 'name']

    def __str__(self):
        tag = " [BOX]" if self.is_box else ""
        return f"{self.name}{tag} — {self.price} FCFA"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING   = 'pending',   'En attente'
        CONFIRMED = 'confirmed', 'Confirmée'
        PREPARING = 'preparing', 'En préparation'
        READY     = 'ready',     'Prête au retrait'
        COMPLETED = 'completed', 'Complétée'
        CANCELLED = 'cancelled', 'Annulée'

    # Client
    customer_name       = models.CharField(max_length=200, verbose_name="Nom complet")
    customer_whatsapp   = models.CharField(max_length=20, verbose_name="WhatsApp")
    customer_email      = models.EmailField(blank=True)
    customer_note       = models.TextField(blank=True, verbose_name="Note client")

    # Commande
    status        = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    total_price   = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    pickup_date   = models.DateField(verbose_name="Date de retrait souhaitée")
    pickup_time   = models.TimeField(verbose_name="Heure de retrait souhaitée")

    # Référence unique lisible
    reference = models.CharField(max_length=20, unique=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Commande"
        verbose_name_plural = "Commandes"
        ordering = ['-created_at']

    def __str__(self):
        return f"Cmd #{self.reference} — {self.customer_name} — {self.status}"

    def save(self, *args, **kwargs):
        if not self.reference:
            import random, string
            self.reference = 'AE' + ''.join(random.choices(string.digits, k=6))
        super().save(*args, **kwargs)

    def recalculate_total(self):
        """Recalcule le total depuis les lignes de commande."""
        total = sum(item.line_total for item in self.items.all())
        self.total_price = total
        self.save(update_fields=['total_price'])


class OrderItem(models.Model):
    order   = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=0)

    # Addons sélectionnés au moment de la commande (snapshot JSON)
    selected_addons = models.JSONField(
        default=list,
        help_text="[{id, name, price}, ...] — snapshot au moment de la commande"
    )
    addons_total = models.DecimalField(max_digits=10, decimal_places=0, default=0)

    class Meta:
        verbose_name = "Ligne de commande"
        verbose_name_plural = "Lignes de commande"

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"

    @property
    def line_total(self):
        return (self.unit_price + self.addons_total) * self.quantity


class CodePromo(models.Model):
    code        = models.CharField(max_length=50, unique=True, verbose_name="Code")
    description = models.CharField(max_length=200, blank=True)
    discount_type = models.CharField(max_length=10, choices=[
        ('percent', 'Pourcentage'),
        ('fixed',   'Montant fixe'),
    ], default='percent')
    discount_value = models.DecimalField(max_digits=10, decimal_places=0)
    min_order      = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    max_uses       = models.PositiveIntegerField(default=100)
    used_count     = models.PositiveIntegerField(default=0)
    is_active      = models.BooleanField(default=True)
    expires_at     = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Code promo"
        verbose_name_plural = "Codes promo"

    def __str__(self):
        return f"{self.code} — {self.discount_value}{'%' if self.discount_type == 'percent' else ' FCFA'}"

    def is_valid(self, order_total=0):
        from django.utils import timezone
        if not self.is_active:
            return False, "Ce code promo n'est plus actif."
        if self.used_count >= self.max_uses:
            return False, "Ce code promo a atteint sa limite d'utilisation."
        if self.expires_at and timezone.now() > self.expires_at:
            return False, "Ce code promo a expiré."
        if order_total < self.min_order:
            return False, f"Commande minimum de {self.min_order:,.0f} FCFA requise."
        return True, "Code valide."

    def calculate_discount(self, order_total):
        if self.discount_type == 'percent':
            return min(order_total * self.discount_value / 100, order_total)
        return min(self.discount_value, order_total)
