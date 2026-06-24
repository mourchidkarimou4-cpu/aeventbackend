from rest_framework import viewsets, permissions, parsers, filters
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Article
from .serializers import ArticleListSerializer, ArticleDetailSerializer

class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.filter(is_published=True).order_by('-created_at')
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
        instance.views += 1
        instance.save(update_fields=['views'])
        return Response(self.get_serializer(instance).data)
