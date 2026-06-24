from core.models import SiteSettings
import urllib.parse


def build_whatsapp_url(phone, message):
    encoded = urllib.parse.quote(message)
    return f"https://wa.me/{phone.replace('+', '').replace(' ', '')}?text={encoded}"


def notify_new_order(order):
    try:
        settings = SiteSettings.get()
        if not settings.whatsapp_number:
            return

        items_text = '\n'.join([
            f"  • {item.quantity}x {item.product.name} = {item.line_total:,.0f} FCFA"
            + (f"\n    + {', '.join(a['name'] for a in item.selected_addons)}" if item.selected_addons else '')
            for item in order.items.select_related('product').all()
        ])

        message = (
            f"🛒 NOUVELLE COMMANDE #{order.reference}\n\n"
            f"👤 {order.customer_name}\n"
            f"📱 {order.customer_whatsapp}\n"
            f"📅 Retrait: {order.pickup_date} à {order.pickup_time}\n\n"
            f"🧾 Articles:\n{items_text}\n\n"
            f"💰 TOTAL: {order.total_price:,.0f} FCFA"
        )
        if order.customer_note:
            message += f"\n\n📝 Note: {order.customer_note}"

        # Stocker l'URL WhatsApp sur la commande pour affichage admin
        order._whatsapp_notify_url = build_whatsapp_url(settings.whatsapp_number, message)
        return message

    except Exception as e:
        print(f"Notification error: {e}")
        return None


def notify_new_quote(quote):
    try:
        settings = SiteSettings.get()
        if not settings.whatsapp_number:
            return

        message = (
            f"📋 NOUVEAU DEVIS — {quote.service_type.upper()}\n\n"
            f"👤 {quote.customer_name}\n"
            f"📱 {quote.customer_whatsapp}\n"
            f"📅 Événement: {quote.event_date or 'Non précisé'}\n"
            f"📍 Lieu: {quote.event_location or 'Non précisé'}\n\n"
            f"📝 {quote.event_description or ''}"
        )

        if quote.service_type in ('traiteur', 'both') and quote.catering_details:
            guests = quote.catering_details.get('guests_count', '')
            if guests:
                message += f"\n\n👥 Convives: {guests}"

        return message

    except Exception as e:
        print(f"Notification error: {e}")
        return None
