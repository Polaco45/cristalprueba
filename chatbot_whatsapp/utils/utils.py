import re 
import logging

_logger = logging.getLogger(__name__)
HTML_TAGS = re.compile(r"<[^>]+>")

def normalize_phone(phone):
    phone_norm = phone.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if phone_norm.startswith('549'):
        phone_norm = phone_norm[3:]
    elif phone_norm.startswith('54'):
        phone_norm = phone_norm[2:]
    return phone_norm

def clean_html(text):
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

    # Lista de estados que se consideran como "cotizado"
    estados_validos = ['draft', 'sent', 'sale', 'cancel']

    # Se busca cualquier orden de venta que coincida con los estados de la lista
    cotizaciones_count = SaleOrder.search_count([
        ('partner_id', '=', partner.id),
        ('state', 'in', estados_validos)
    ])
    
    # Se buscan las ventas en el punto de venta (POS)
    ventas_pos_count = PosOrder.search_count([
        ('partner_id', '=', partner.id)
    ])

    _logger.info(
        "📌 Evaluando cotización — Partner: %s | Órdenes de Venta: %s | Órdenes de POS: %s",
        partner.name, cotizaciones_count, ventas_pos_count
    )

    # El cliente se considera cotizado si tiene al menos una orden de venta o una orden de POS
    return cotizaciones_count > 0 or ventas_pos_count > 0