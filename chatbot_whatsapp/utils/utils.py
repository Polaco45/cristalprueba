# utils.py
import re
import logging

_logger = logging.getLogger(__name__)
HTML_TAGS = re.compile(r"<[^>]+>")

def sanitize_phone(phone):
    """Elimina todos los caracteres que no sean dígitos de un número de teléfono."""
    return re.sub(r'\D', '', phone or '')

def normalize_phone(phone):
    """
    Normaliza un número de teléfono a un formato local estándar para Argentina,
    eliminando el código de país y el '9' de los móviles.
    Ejemplo: '+54 9 358 123-4567' -> '3581234567'
    """
    sanitized = sanitize_phone(phone)
    if sanitized.startswith('549'):
        # Quita el código de país '54' y el prefijo móvil '9'
        return sanitized[3:]
    if sanitized.startswith('54'):
        # Quita solo el código de país '54'
        return sanitized[2:]
    return sanitized

def find_partner_by_phone(env, phone_number):
    """
    Encuentra un partner por número de teléfono, ignorando formato, espacios y prefijos.
    Esta es la lógica central para prevenir la creación de contactos duplicados.

    :param env: El entorno de Odoo.
    :param phone_number: El número de teléfono entrante (sin procesar).
    :return: Un recordset de res.partner (puede estar vacío si no se encuentra).
    """
    if not phone_number:
        return env['res.partner']

    # 1. Normaliza el número entrante a su forma base (ej: '3584840089').
    normalized_in_phone = normalize_phone(phone_number)
    if not normalized_in_phone:
        return env['res.partner']

    _logger.info(f"🔍 Búsqueda de partner. Entrada: '{phone_number}', Normalizado: '{normalized_in_phone}'.")

    # 2. Busca partners candidatos usando los últimos 8 dígitos para optimizar.
    search_term = normalized_in_phone[-8:]
    domain = ['|', ('phone', 'ilike', search_term), ('mobile', 'ilike', search_term)]
    candidate_partners = env['res.partner'].sudo().search(domain)

    # 3. Itera sobre los candidatos y compara sus números normalizados.
    for partner in candidate_partners:
        db_phone_normalized = normalize_phone(partner.phone)
        db_mobile_normalized = normalize_phone(partner.mobile)

        if normalized_in_phone == db_phone_normalized or normalized_in_phone == db_mobile_normalized:
            _logger.info(f"✅ Partner encontrado: '{partner.name}' (ID: {partner.id}) coincide.")
            return partner # Devuelve el primer partner que coincida

    _logger.info(f"🚫 No se encontró un partner existente para '{normalized_in_phone}'.")
    return env['res.partner'] # Devuelve un recordset vacío si no hay coincidencias

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