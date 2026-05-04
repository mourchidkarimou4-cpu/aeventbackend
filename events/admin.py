from django.contrib import admin
from django.utils.html import format_html
from .models import QuoteRequest, PrintFile


class PrintFileInline(admin.TabularInline):
    model = PrintFile
    extra = 0
    readonly_fields = ['original_filename', 'file_size_kb', 'uploaded_at', 'file_preview']
    can_delete = False
    fields = ['file_preview', 'original_filename', 'file_size_kb', 'description', 'uploaded_at']

    def file_preview(self, obj):
        if obj.file and obj.original_filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            return format_html('<img src="{}" style="height:48px;border-radius:6px">', obj.file.url)
        return format_html('<span style="font-size:20px">📄</span>')
    file_preview.short_description = 'Aperçu'


@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    list_display = ['customer_name', 'customer_whatsapp', 'service_type_badge', 'status', 'status_badge', 'event_date', 'quote_amount_display', 'created_at']
    list_filter = ['service_type', 'status', 'event_date']
    search_fields = ['customer_name', 'customer_whatsapp', 'customer_email']
    list_editable = ['status']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [PrintFileInline]

    fieldsets = [
        ('Client', {
            'fields': ('customer_name', 'customer_whatsapp', 'customer_email')
        }),
        ('Demande', {
            'fields': ('service_type', 'status', 'event_date', 'event_location', 'event_description', 'additional_note')
        }),
        ('Détails Traiteur', {
            'fields': ('catering_details',),
            'classes': ('collapse',),
        }),
        ('Détails Imprimerie', {
            'fields': ('print_details',),
            'classes': ('collapse',),
        }),
        ('Réponse devis', {
            'fields': ('quote_amount', 'quote_message', 'quote_sent_at')
        }),
        ('Méta', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    ]

    def service_type_badge(self, obj):
        colors = {
            'traiteur':   '#8b5cf6',
            'imprimerie': '#3b82f6',
            'both':       '#ff6b00',
        }
        color = colors.get(obj.service_type, '#ccc')
        return format_html(
            '<span style="background:{};color:white;padding:3px 12px;border-radius:100px;font-size:11px;font-weight:600">{}</span>',
            color, obj.get_service_type_display()
        )
    service_type_badge.short_description = 'Service'

    def status_badge(self, obj):
        colors = {
            'new':       '#3b82f6',
            'reviewing': '#8b5cf6',
            'quoted':    '#f59e0b',
            'accepted':  '#10b981',
            'rejected':  '#ef4444',
            'completed': '#6b7280',
        }
        color = colors.get(obj.status, '#ccc')
        return format_html(
            '<span style="background:{};color:white;padding:3px 12px;border-radius:100px;font-size:11px;font-weight:600">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Statut'

    def quote_amount_display(self, obj):
        if obj.quote_amount:
            return format_html('<strong style="color:#10b981">{:,.0f} FCFA</strong>', obj.quote_amount)
        return format_html('<span style="color:#ccc">—</span>')
    quote_amount_display.short_description = 'Devis'
