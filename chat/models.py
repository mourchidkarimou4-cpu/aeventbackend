from django.db import models

class MessageChat(models.Model):
    session_id  = models.CharField(max_length=100, db_index=True)
    client_nom  = models.CharField(max_length=100, blank=True)
    client_wa   = models.CharField(max_length=20, blank=True)
    contenu     = models.TextField()
    is_admin    = models.BooleanField(default=False)
    is_read     = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Message chat"
        verbose_name_plural = "Messages chat"
        ordering = ['created_at']

    def __str__(self):
        return f"{'Admin' if self.is_admin else self.client_nom} — {self.contenu[:50]}"
