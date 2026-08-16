from rest_framework import viewsets, permissions, parsers, filters
from rest_framework.response import Response
from django.db.models import F
from django_filters.rest_framework import DjangoFilterBackend
from .models import Article
from .serializers import ArticleListSerializer, ArticleDetailSerializer

class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.filter(is_published=True).order_by('-created_at')
    lookup_field = 'slug'
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category']
    search_fields = ['title', 'content', 'excerpt']

    def get_permissions(self):
        if self.request.method in ['GET', 'HEAD', 'OPTIONS']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        if self.request.user and self.request.user.is_staff:
            return Article.objects.all().order_by('-created_at')
        return Article.objects.filter(is_published=True).order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ArticleDetailSerializer
        return ArticleListSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Compteur de vues : une seule vue par session pour éviter l'inflation
        # par les rafraîchissements et les bots sans throttle bloquant.
        viewed_key = f'blog_viewed_{instance.pk}'
        if not request.session.get(viewed_key):
            Article.objects.filter(pk=instance.pk).update(views=F('views') + 1)
            request.session[viewed_key] = True
        instance.refresh_from_db(fields=['views'])
        return Response(self.get_serializer(instance).data)
