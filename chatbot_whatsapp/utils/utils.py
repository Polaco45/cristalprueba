import re 
import logging

_logger = logging.getLogger(__name__)
HTML_TAGS = re.compile(r"<[^>]+>")

def normalize_phone(phone: str) -> str:
    """Quita todo lo que no sea dígito y deja solo el número en formato simple.
    Ejemplo: '+54 9 11 1234-5678' -> '5491112345678'
    """
    if not phone:
        return ''
    # Sacar todo menos números
    digits = re.sub(r'\D', '', phone)
    return digits

def clean_html(text):
    return re.sub(HTML_TAGS, "", text or "").strip()