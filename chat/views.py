from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import MessageChat
from .serializers import MessageChatSerializer


class MessageChatViewSet(viewsets.ModelViewSet):
    serializer_class = MessageChatSerializer

    def get_permissions(self):
        if self.action in ['session', 'create']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        return MessageChat.objects.all()

    @action(detail=False, methods=['get', 'post'], permission_classes=[permissions.AllowAny])
    def session(self, request):
        session_id = request.query_params.get('id') or request.data.get('session_id')
        if not session_id:
            return Response({'error': 'session_id requis.'}, status=400)

        if request.method == 'POST':
            data = request.data.copy()
            data['session_id'] = session_id
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=201)

        messages = MessageChat.objects.filter(session_id=session_id)
        messages.filter(is_admin=True, is_read=False).update(is_read=True)
        return Response(self.get_serializer(messages, many=True).data)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAdminUser])
    def sessions(self, request):
        from django.db.models import Max, Count, Q
        sessions = MessageChat.objects.values('session_id').annotate(
            last_message=Max('created_at'),
            unread=Count('id', filter=Q(is_admin=False, is_read=False))
        ).order_by('-last_message')
        result = []
        for s in sessions:
            last = MessageChat.objects.filter(session_id=s['session_id']).last()
            result.append({
                'session_id': s['session_id'],
                'client_nom': last.client_nom if last else '',
                'client_wa': last.client_wa if last else '',
                'last_message': last.contenu[:60] if last else '',
                'last_at': s['last_message'],
                'unread': s['unread'],
            })
        return Response(result)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def reply(self, request):
        session_id = request.data.get('session_id')
        contenu = request.data.get('contenu')
        if not session_id or not contenu:
            return Response({'error': 'session_id et contenu requis.'}, status=400)
        msg = MessageChat.objects.create(
            session_id=session_id,
            contenu=contenu,
            is_admin=True,
            client_nom="A'Events",
        )
        return Response(MessageChatSerializer(msg).data, status=201)
