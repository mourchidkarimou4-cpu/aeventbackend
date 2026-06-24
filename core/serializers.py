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

def absolute_file_url(request, value):
    if not value:
        return None
    try:
        url = value.url
    except Exception:
        url = str(value)
    if not url:
        return None
    if url.startswith(('http://', 'https://')):
        return url
    if request:
        return request.build_absolute_uri(url)
    return url

class GaleriePhotoSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    image = serializers.CharField(required=False, allow_blank=True)
    image_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = GaleriePhoto
        fields = ['id', 'title', 'category', 'category_display', 'image', 'image_url', 'order', 'is_active', 'created_at']

    def get_image_url(self, obj):
        return absolute_file_url(self.context.get('request'), obj.image)
