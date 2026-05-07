from rest_framework import serializers
from .models import Article

class ArticleListSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    class Meta:
        model = Article
        fields = ['id', 'title', 'slug', 'category', 'category_display', 'excerpt', 'image', 'views', 'created_at']

class ArticleDetailSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    class Meta:
        model = Article
        fields = '__all__'
