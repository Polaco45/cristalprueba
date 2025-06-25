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
    if not partner:
        return False

    SaleOrder = partner.env['sale.order'].sudo()
    PosOrder = partner.env['pos.order'].sudo()

    cotizaciones = SaleOrder.search_count([
        ('partner_id', '=', partner.id),
        ('state', '=', 'draft')  # solo presupuestos (no confirmados)
    ])
    
    ventas_pos = PosOrder.search_count([
        ('partner_id', '=', partner.id)
    ])

    _logger.info("📌 Evaluando cotización — Partner: %s | Cotizaciones: %s | POS: %s",
                 partner.name, cotizaciones, ventas_pos)

    return cotizaciones > 0 or ventas_pos > 0