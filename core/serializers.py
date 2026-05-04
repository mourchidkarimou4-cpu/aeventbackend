from rest_framework import serializers
from .models import SiteSettings

class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = [
            'whatsapp_number', 'whatsapp_message_default',
            'address', 'email_contact',
            'instagram_url', 'facebook_url', 'tiktok_url',
            'tagline', 'hero_subtitle',
            'momo_number', 'momo_name',
        ]


from .models import GaleriePhoto

class GaleriePhotoSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    class Meta:
        model = GaleriePhoto
        fields = ['id', 'title', 'category', 'category_display', 'image', 'order', 'is_active', 'created_at']
