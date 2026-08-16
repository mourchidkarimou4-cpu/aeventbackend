from .models import Order, CodePromo, BonCadeau


def apply_status_transition(order, new_status):
    """Applique une transition de statut avec ses effets de bord.

    Annulation : restitue le stock et remet le code promo / bon cadeau à
    disposition. Réactivation : re-réserve le stock et re-consomme le code
    promo / bon cadeau (après validation de disponibilité).

    Retourne (True, None) en cas de succès, sinon (False, message_erreur).
    """
    if new_status == order.status:
        return True, None

    if new_status == Order.Status.CANCELLED and order.status != Order.Status.CANCELLED:
        _restore(order)
    elif order.status == Order.Status.CANCELLED and new_status != Order.Status.CANCELLED:
        ok, error = _reactivate(order)
        if not ok:
            return False, error
    order.status = new_status
    return True, None


def _restore(order):
    for item in order.items.select_related('product'):
        product = item.product
        if product.stock is not None:
            product.stock += item.quantity
            product.save(update_fields=['stock'])
    if order.promo_code:
        try:
            promo = CodePromo.objects.get(code__iexact=order.promo_code)
            promo.used_count = max(0, promo.used_count - 1)
            promo.save(update_fields=['used_count'])
        except CodePromo.DoesNotExist:
            pass
    if order.bon_code:
        BonCadeau.objects.filter(code__iexact=order.bon_code).update(is_used=False)


def _reactivate(order):
    # Valider tout AVANT de muter quoi que ce soit
    for item in order.items.select_related('product'):
        product = item.product
        if product.stock is not None and product.stock < item.quantity:
            return False, (
                f"Stock insuffisant pour « {product.name} » "
                f"(stock restant : {product.stock})."
            )

    promo = None
    if order.promo_code:
        try:
            promo = CodePromo.objects.get(code__iexact=order.promo_code)
        except CodePromo.DoesNotExist:
            promo = None
        if promo:
            valid, message = promo.is_valid(order.total_price)
            if not valid:
                return False, f"Code promo « {promo.code} » : {message}."

    bon = None
    if order.bon_code:
        try:
            bon = BonCadeau.objects.get(code__iexact=order.bon_code)
        except BonCadeau.DoesNotExist:
            bon = None
        if bon:
            if bon.is_used:
                return False, f"Le bon cadeau « {bon.code} » a été utilisé ailleurs."
            if not bon.is_paid:
                return False, f"Le bon cadeau « {bon.code} » n'a pas été payé."

    for item in order.items.select_related('product'):
        product = item.product
        if product.stock is not None:
            product.stock -= item.quantity
            product.save(update_fields=['stock'])
    if promo:
        promo.used_count += 1
        promo.save(update_fields=['used_count'])
    if bon:
        bon.is_used = True
        bon.save(update_fields=['is_used'])
    return True, None
