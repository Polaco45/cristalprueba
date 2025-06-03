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