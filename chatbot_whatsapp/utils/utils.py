import re 
import logging

_logger = logging.getLogger(__name__)
HTML_TAGS = re.compile(r"<[^>]+>")

def normalize_phone(phone_number):
    """
    Limpia y normaliza un número de teléfono de Argentina a un formato estándar de 10 dígitos.
    - Elimina todos los caracteres no numéricos.
    - Maneja prefijos comunes como '+54', '54', '9', '15' y '0'.
    El objetivo es obtener siempre el formato de 10 dígitos (código de área + número).
    Ej: '+54 9 358 123-4567' -> '3581234567'
    """
    if not phone_number:
        return ""
    
    # 1. Conservar solo los dígitos
    cleaned_phone = re.sub(r'\D', '', str(phone_number))
    
    # 2. Si empieza con el código de país '54', lo quitamos para analizar el resto
    if cleaned_phone.startswith('54'):
        cleaned_phone = cleaned_phone[2:]
        
    # 3. Si después del código de país viene un '9' (celular), lo quitamos
    if cleaned_phone.startswith('9'):
        cleaned_phone = cleaned_phone[1:]
        
    # 4. Si el número local empieza con '15' o '0', lo quitamos
    if cleaned_phone.startswith('15'):
         cleaned_phone = cleaned_phone[2:]
    elif cleaned_phone.startswith('0'):
         cleaned_phone = cleaned_phone[1:]

    # Devolvemos el número. Si es más largo de 10 (ej. BsAs), nos quedamos con los últimos 10.
    return cleaned_phone[-10:] if len(cleaned_phone) > 10 else cleaned_phone

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