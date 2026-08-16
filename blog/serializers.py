from rest_framework import serializers
from .models import Article
from core.validators import drf_validate_magic, IMAGE_MIMES
from core.fields import AbsoluteUrlField

class ArticleListSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    image = AbsoluteUrlField(required=False, allow_null=True)

    class Meta:
        model = Article
        fields = ['id', 'title', 'slug', 'category', 'category_display', 'excerpt', 'image', 'views', 'created_at']

    def validate_image(self, value):
        drf_validate_magic(value, IMAGE_MIMES, 'Image')
        return value

class ArticleDetailSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    image = AbsoluteUrlField(required=False, allow_null=True)

    class Meta:
        model = Article
        fields = '__all__'
