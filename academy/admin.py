from django.contrib import admin
from django.utils.html import format_html
from .models import Formation, Reservation


class ReservationInline(admin.TabularInline):
    model = Reservation
    extra = 0
    readonly_fields = ['reference', 'participant_name', 'participant_whatsapp', 'status', 'amount_paid', 'payment_method', 'created_at']
    can_delete = False
    fields = ['reference', 'participant_name', 'participant_whatsapp', 'status', 'amount_paid', 'payment_method']


@admin.register(Formation)
class FormationAdmin(admin.ModelAdmin):
    list_display = ['title', 'start_datetime', 'available_seats_display', 'fill_bar', 'price_display', 'status', 'is_featured']
    list_editable = ['status', 'is_featured']
    list_filter = ['status', 'level', 'is_online', 'is_featured']
    search_fields = ['title', 'instructor_name', 'description']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ReservationInline]
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = [
        ('Informations', {
            'fields': ('title', 'slug', 'short_desc', 'description', 'image', 'instructor_name', 'level')
        }),
        ('Programme', {
            'fields': ('program_details', 'what_you_learn', 'prerequisites'),
            'classes': ('collapse',),
        }),
        ('Logistique', {
            'fields': ('location', 'is_online', 'start_datetime', 'end_datetime', 'duration_label')
        }),
        ('Places & Tarif', {
            'fields': ('total_seats', 'reserved_seats', 'price', 'early_bird_price', 'early_bird_deadline')
        }),
        ('Statut', {
            'fields': ('status', 'is_featured', 'created_at', 'updated_at')
        }),
    ]

    def available_seats_display(self, obj):
        avail = obj.available_seats
        total = obj.total_seats
        color = '#ef4444' if avail == 0 else '#10b981' if avail > 3 else '#f59e0b'
        return format_html(
            '<span style="color:{};font-weight:700">{}/{}</span>',
            color, avail, total
        )
    available_seats_display.short_description = 'Places dispo'

    def fill_bar(self, obj):
        pct = obj.fill_percentage
        color = '#10b981' if pct < 70 else '#f59e0b' if pct < 90 else '#ef4444'
        return format_html(
            '<div style="background:#eee;border-radius:4px;width:100px;height:8px">'
            '<div style="background:{};border-radius:4px;width:{}%;height:100%"></div>'
            '</div> <span style="font-size:11px;color:#666">{}%</span>',
            color, pct, pct
        )
    fill_bar.short_description = 'Remplissage'

    def price_display(self, obj):
        return format_html('<strong style="color:#ff6b00">{:,.0f} FCFA</strong>', obj.price)
    price_display.short_description = 'Prix'


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ['reference', 'participant_name', 'participant_whatsapp', 'formation', 'status', 'status_badge', 'amount_paid_display', 'payment_method', 'created_at']
    list_filter = ['status', 'formation', 'payment_method']
    search_fields = ['reference', 'participant_name', 'participant_whatsapp']
    readonly_fields = ['reference', 'created_at', 'updated_at']
    list_editable = ['status']

    fieldsets = [
        ('Participant', {
            'fields': ('participant_name', 'participant_whatsapp', 'participant_email', 'participant_note')
        }),
        ('Réservation', {
            'fields': ('formation', 'reference', 'status')
        }),
        ('Paiement', {
            'fields': ('amount_paid', 'payment_method', 'payment_ref', 'payment_date')
        }),
        ('Méta', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    ]

    def status_badge(self, obj):
        colors = {
            'pending':   '#f59e0b',
            'confirmed': '#3b82f6',
            'paid':      '#10b981',
            'cancelled': '#ef4444',
            'waitlist':  '#8b5cf6',
        }
        color = colors.get(obj.status, '#ccc')
        return format_html(
            '<span style="background:{};color:white;padding:3px 12px;border-radius:100px;font-size:11px;font-weight:600">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Statut'

    def amount_paid_display(self, obj):
        if obj.amount_paid:
            return format_html('<strong style="color:#10b981">{:,.0f} FCFA</strong>', obj.amount_paid)
        return format_html('<span style="color:#ccc">—</span>')
    amount_paid_display.short_description = 'Montant payé'
