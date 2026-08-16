from core.models import SiteSettings
import urllib.parse
import logging

logger = logging.getLogger(__name__)


def build_whatsapp_url(phone, message):
    encoded = urllib.parse.quote(message)
    return f"https://wa.me/{phone.replace('+', '').replace(' ', '')}?text={encoded}"


def build_order_message(order, items=None):
    # items optionnel : permet de réutiliser le prefetch_related du queryset
    # (évite une requête supplémentaire par commande lors de la sérialisation)
    if items is None:
        items = order.items.select_related('product').all()
    items_text = '\n'.join([
        f"  • {item.quantity}x {item.product.name} = {item.line_total:,.0f} FCFA"
        + (f"\n    + {', '.join(a['name'] for a in item.selected_addons)}" if item.selected_addons else '')
        for item in items
    ])

    message = (
        f"🛒 NOUVELLE COMMANDE #{order.reference}\n\n"
        f"👤 {order.customer_name}\n"
        f"📱 {order.customer_whatsapp}\n"
        f"📅 Retrait: {order.pickup_date} à {order.pickup_time}\n\n"
        f"🧾 Articles:\n{items_text}\n\n"
        f"💰 TOTAL: {order.total_price:,.0f} FCFA"
    )
    if order.discount_amount:
        message += f"\n🎁 Réduction: {order.discount_amount:,.0f} FCFA"
    if order.customer_note:
        message += f"\n\n📝 Note: {order.customer_note}"
    return message


def order_whatsapp_notify_url(order, items=None):
    try:
        settings = SiteSettings.get()
        if not settings.whatsapp_number:
            return None
        return build_whatsapp_url(settings.whatsapp_number, build_order_message(order, items=items))
    except Exception:
        return None


def build_quote_message(quote):
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

    if quote.service_type in ('imprimerie', 'both') and quote.print_details:
        print_type = quote.print_details.get('print_type', '')
        if print_type:
            message += f"\n\n🖨️ Type: {print_type}"

    return message


def quote_whatsapp_notify_url(quote):
    try:
        settings = SiteSettings.get()
        if not settings.whatsapp_number:
            return None
        return build_whatsapp_url(settings.whatsapp_number, build_quote_message(quote))
    except Exception:
        return None


def notify_new_order(order):
    try:
        message = build_order_message(order)
        settings = SiteSettings.get()
        if settings.whatsapp_number:
            return build_whatsapp_url(settings.whatsapp_number, message)
        return message
    except Exception as e:
        logger.error(f"Notification error: {e}")
        return None


def notify_new_quote(quote):
    try:
        message = build_quote_message(quote)
        settings = SiteSettings.get()
        if settings.whatsapp_number:
            return build_whatsapp_url(settings.whatsapp_number, message)
        return message
    except Exception as e:
        logger.error(f"Notification error: {e}")
        return None
