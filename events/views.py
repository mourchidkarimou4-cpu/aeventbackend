from rest_framework import viewsets, permissions, status, parsers
from rest_framework.response import Response
from .models import QuoteRequest, PrintFile
from .serializers import QuoteRequestSerializer, PrintFileSerializer


class QuoteRequestViewSet(viewsets.ModelViewSet):
    queryset = QuoteRequest.objects.all().prefetch_related('print_files')

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_serializer_class(self):
        return QuoteRequestSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quote = serializer.save()
        try:
            from shop.notifications import notify_new_quote
            notify_new_quote(quote)
        except Exception:
            pass
        return Response(
            QuoteRequestSerializer(quote, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class PrintFileUploadView(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def create(self, request):
        files = request.FILES.getlist('files')
        if not files:
            return Response({'error': 'Aucun fichier fourni.'}, status=400)
        if len(files) > 5:
            return Response({'error': 'Maximum 5 fichiers par envoi.'}, status=400)

        created = []
        errors = []
        for f in files:
            serializer = PrintFileSerializer(
                data={'file': f, 'description': request.data.get('description', '')}
            )
            if serializer.is_valid():
                pf = serializer.save()
                created.append(PrintFileSerializer(pf).data)
            else:
                errors.append({'file': f.name, 'errors': serializer.errors})

        return Response({
            'uploaded': created,
            'errors': errors,
        }, status=201 if created else 400)
