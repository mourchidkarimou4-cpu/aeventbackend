## ─── shop/admin.py ──────────────────────────────────────────────────────────

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import Category, Addon, Product, Order, OrderItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'slug', 'product_count', 'is_active', 'order']
    list_editable = ['is_active', 'order']
    prepopulated_fields = {'slug': ('name',)}

    def product_count(self, obj):
        return obj.products.filter(is_available=True).count()
    product_count.short_description = 'Produits dispo'


@admin.register(Addon)
class AddonAdmin(admin.ModelAdmin):
    list_display  = ['name', 'price', 'is_active']
    list_editable = ['price', 'is_active']


class AddonInline(admin.TabularInline):
    model  = Product.available_addons.through
    extra  = 1
    verbose_name = "Accompagnement lié"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display   = ['name', 'category', 'price', 'is_box', 'is_available', 'is_featured', 'stock', 'preview_image']
    list_editable  = ['price', 'is_available', 'is_featured', 'stock']
    list_filter    = ['category', 'is_box', 'is_available', 'is_featured']
    search_fields  = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal   = ['available_addons']
    fieldsets = [
        ('Informations produit', {
            'fields': ('name', 'slug', 'category', 'description', 'image', 'image_gallery')
        }),
        ('Tarif & disponibilité', {
            'fields': ('price', 'is_available', 'is_featured', 'stock', 'min_quantity', 'preparation_time_hours')
        }),
        ('Coffret / Box', {
            'fields': ('is_box', 'box_contents'),
            'classes': ('collapse',),
        }),
        ('Accompagnements', {
            'fields': ('available_addons',)
        }),
    ]

    def preview_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:40px;border-radius:4px">', obj.image.url)
        return '—'
    preview_image.short_description = 'Photo'


class OrderItemInline(admin.TabularInline):
    model  = OrderItem
    extra  = 0
    readonly_fields = ['product', 'quantity', 'unit_price', 'selected_addons', 'addons_total', 'line_total_display']
    can_delete = False

    def line_total_display(self, obj):
        return f"{obj.line_total:,.0f} FCFA"
    line_total_display.short_description = 'Total ligne'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display   = [
        'reference', 'customer_name', 'customer_whatsapp',
        'status', 'status_badge', 'total_price_display',
        'pickup_date', 'pickup_time', 'created_at'
    ]
    list_filter    = ['status', 'pickup_date', 'created_at']
    search_fields  = ['reference', 'customer_name', 'customer_whatsapp']
    list_editable  = ['status']  # Mise à jour rapide du statut dans la liste
    readonly_fields = ['reference', 'total_price', 'created_at', 'updated_at']
    inlines        = [OrderItemInline]
    date_hierarchy = 'created_at'

    fieldsets = [
        ('Référence', {'fields': ('reference', 'status', 'created_at', 'updated_at')}),
        ('Client', {'fields': ('customer_name', 'customer_whatsapp', 'customer_email', 'customer_note')}),
        ('Retrait', {'fields': ('pickup_date', 'pickup_time')}),
        ('Montant', {'fields': ('total_price',)}),
    ]

    def status_badge(self, obj):
        colors = {
            'pending':   '#f59e0b',
            'confirmed': '#3b82f6',
            'preparing': '#8b5cf6',
            'ready':     '#10b981',
            'completed': '#6b7280',
            'cancelled': '#ef4444',
        }
        color = colors.get(obj.status, '#ccc')
        return format_html(
            '<span style="background:{};color:white;padding:2px 10px;border-radius:12px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Statut'

    def total_price_display(self, obj):
        return format_html('<strong>{:,.0f} FCFA</strong>', obj.total_price)
    total_price_display.short_description = 'Total'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('items')
