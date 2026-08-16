import logging
from rest_framework import viewsets, permissions, status, parsers
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from .models import QuoteRequest, PrintFile
from .serializers import QuoteRequestSerializer, PrintFileUploadSerializer

logger = logging.getLogger(__name__)

MAX_FILES_PER_REQUEST = 5
MAX_TOTAL_SIZE_MB = 60
ORPHAN_TTL_HOURS = 24


class QuoteRequestViewSet(viewsets.ModelViewSet):
    queryset = QuoteRequest.objects.all().prefetch_related('print_files')

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_throttles(self):
        if self.action == 'create':
            self.throttle_scope = 'quote_create'
            return [ScopedRateThrottle()]
        return []

    def get_serializer_class(self):
        return QuoteRequestSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quote = serializer.save()
        try:
            from shop.notifications import notify_new_quote
            notify_new_quote(quote)
        except Exception as e:
            logger.exception("Erreur notify_new_quote: %s", e)
        return Response(
            QuoteRequestSerializer(quote, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class PrintFileUploadView(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    throttle_scope = 'file_upload'

    def create(self, request):
        from django.utils import timezone
        from datetime import timedelta
        # Purge des fichiers orphelins (jamais rattachés à un devis) trop anciens
        cutoff = timezone.now() - timedelta(hours=ORPHAN_TTL_HOURS)
        PrintFile.objects.filter(
            quote_request__isnull=True,
            uploaded_at__lt=cutoff,
        ).delete()

        files = request.FILES.getlist('files')
        if not files:
            return Response({'error': 'Aucun fichier fourni.'}, status=400)
        if len(files) > MAX_FILES_PER_REQUEST:
            return Response({'error': 'Maximum 5 fichiers par envoi.'}, status=400)

        total_size = sum(f.size for f in files)
        if total_size > MAX_TOTAL_SIZE_MB * 1024 * 1024:
            return Response(
                {'error': f'Taille totale maximale : {MAX_TOTAL_SIZE_MB} Mo par envoi.'},
                status=400
            )

        created = []
        errors = []
        for f in files:
            serializer = PrintFileUploadSerializer(
                data={'file': f, 'description': request.data.get('description', '')}
            )
            if serializer.is_valid():
                pf = serializer.save()
                created.append(PrintFileUploadSerializer(pf).data)
            else:
                errors.append({'file': f.name, 'errors': serializer.errors})

        return Response({
            'uploaded': created,
            'errors': errors,
        }, status=201 if created else 400)
