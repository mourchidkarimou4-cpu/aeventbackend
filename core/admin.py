from django.contrib import admin
from django.utils.html import format_html
from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Contact & Réseaux', {
            'fields': ('whatsapp_number', 'whatsapp_message_default', 'email_contact', 'address')
        }),
        ('Réseaux sociaux', {
            'fields': ('instagram_url', 'facebook_url', 'tiktok_url')
        }),
        ('Textes marketing', {
            'fields': ('tagline', 'hero_subtitle')
        }),
        ('Paiement Mobile Money', {
            'fields': ('momo_number', 'momo_name')
        }),
    ]

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Redirige directement vers l'édition du singleton
        obj, _ = SiteSettings.objects.get_or_create(pk=1)
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(
            reverse('admin:core_sitesettings_change', args=[obj.pk])
        )
