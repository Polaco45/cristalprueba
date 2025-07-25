# utils.py
import re
import logging

_logger = logging.getLogger(__name__)
HTML_TAGS = re.compile(r"<[^>]+>")

def sanitize_for_search(phone):
    """
    Sanitiza un número de teléfono al formato E.164 para buscar en el campo
    'phone_sanitized' de Odoo. Ej: '+54 9 358...' -> '+549358...'
    """
    if not phone:
        return ''
    # Mantiene solo los dígitos y antepone un '+'
    return '+' + re.sub(r'\D', '', phone or '')

def get_local_number(phone):
    """
    Obtiene la representación local de un número de Argentina, sin código de país ni '9'.
    Se usa para mostrar nombres amigables. Ej: '+549358...' -> '358...'
    """
    sanitized = re.sub(r'\D', '', phone or '')
    if sanitized.startswith('549'):
        return sanitized[3:]
    if sanitized.startswith('54'):
        return sanitized[2:]
    return sanitized

def clean_html(text):
    """Limpia las etiquetas HTML de un texto."""
    return re.sub(HTML_TAGS, "", text or "").strip()

def is_cotizado(partner):
    """
    Verifica si un partner tiene alguna orden de venta en estados específicos
    o alguna orden de punto de venta.
    """
    if not partner:
        return False

    SaleOrder = partner.env['sale.order'].sudo()
    PosOrder = partner.env['pos.order'].sudo()
    estados_validos = ['draft', 'sent', 'sale', 'cancel']

    cotizaciones_count = SaleOrder.search_count([
        ('partner_id', '=', partner.id),
        ('state', 'in', estados_validos)
    ])
    
    ventas_pos_count = PosOrder.search_count([
        ('partner_id', '=', partner.id)
    ])

    _logger.info(
        "📌 Evaluando cotización — Partner: %s | Órdenes de Venta: %s | Órdenes de POS: %s",
        partner.name, cotizaciones_count, ventas_pos_count
    )

    return cotizaciones_count > 0 or ventas_pos_count > 0