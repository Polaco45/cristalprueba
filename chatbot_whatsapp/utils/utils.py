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

# ——— Evalúa si está cotizado ———
def is_cotizado(partner):
    if not partner:
        return False

    pricelist = partner.property_product_pricelist
    pricelist_name = pricelist.name if pricelist else False
    tags = partner.category_id.mapped('name')

    _logger.info("📌 Evaluando cotización — Partner: %s | Pricelist: %s | Tags: %s",
    partner.name, pricelist_name, tags)

    if pricelist_name == "Lista Clientes" and any(t in tags for t in ["Tipo de Cliente / EMPRESA", "Tipo de Cliente / Mayorista"]):
        return False

    return bool(pricelist)