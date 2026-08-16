import re
import uuid

from django.db.models import Max, Count, Q
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .models import MessageChat
from .serializers import MessageChatSerializer, MessageChatPublicSerializer


SESSION_ID_PATTERN = re.compile(r'^(sess-[A-Za-z0-9_-]{6,64}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$')


def _is_valid_session_id(value):
    return bool(value) and bool(SESSION_ID_PATTERN.match(value))


class MessageChatViewSet(viewsets.ModelViewSet):
    serializer_class = MessageChatSerializer

    def get_permissions(self):
        if self.action == 'session':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_throttles(self):
        if self.action == 'session' and self.request.method == 'POST':
            self.throttle_scope = 'chat_post'
            return [ScopedRateThrottle()]
        return []

    def get_queryset(self):
        return MessageChat.objects.all()

    @action(detail=False, methods=['get', 'post'], permission_classes=[permissions.AllowAny])
    def session(self, request):
        session_id = request.query_params.get('id') or request.data.get('session_id')
        if not _is_valid_session_id(session_id):
            return Response({'error': 'session_id invalide.'}, status=400)

        if request.method == 'POST':
            data = request.data.copy()
            data['session_id'] = session_id
            data['is_admin'] = False
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(MessageChatPublicSerializer(serializer.instance).data, status=201)

        messages = MessageChat.objects.filter(session_id=session_id)
        messages.filter(is_admin=True, is_read=False).update(is_read=True)
        return Response(MessageChatPublicSerializer(messages, many=True).data)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAdminUser])
    def sessions(self, request):
        # 2 passes pour éviter le N+1
        sessions = MessageChat.objects.values('session_id').annotate(
            last_at=Max('created_at'),
            unread=Count('id', filter=Q(is_admin=False, is_read=False))
        ).order_by('-last_at')

        ids = [s['session_id'] for s in sessions]
        last_by_session = {}
        if ids:
            for last in MessageChat.objects.filter(session_id__in=ids).order_by('created_at'):
                last_by_session[last.session_id] = last

        result = []
        for s in sessions:
            last = last_by_session.get(s['session_id'])
            result.append({
                'session_id': s['session_id'],
                'client_nom': last.client_nom if last else '',
                'client_wa': last.client_wa if last else '',
                'last_message': last.contenu[:60] if last else '',
                'last_at': s['last_at'],
                'unread': s['unread'],
            })
        return Response(result)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def reply(self, request):
        session_id = request.data.get('session_id')
        contenu = request.data.get('contenu')
        if not _is_valid_session_id(session_id):
            return Response({'error': 'session_id invalide.'}, status=400)
        if not contenu:
            return Response({'error': 'session_id et contenu requis.'}, status=400)
        if len(contenu) > 2000:
            return Response({'error': 'Message trop long (2000 caractères max).'}, status=400)
        msg = MessageChat.objects.create(
            session_id=session_id,
            contenu=contenu,
            is_admin=True,
            client_nom="A'Events",
        )
        return Response(MessageChatSerializer(msg).data, status=201)
