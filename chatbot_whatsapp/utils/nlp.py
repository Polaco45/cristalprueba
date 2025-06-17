import openai
import logging
from ..config.config import general_config

_logger = logging.getLogger(__name__)

def detect_intention(user_text, api_key):
    """Clasifica la intención del usuario."""
    openai.api_key = api_key

    system = (
        "Eres un clasificador de intenciones para un chatbot de atención al cliente "
        "de una tienda de productos de limpieza.\n"
        "Las categorías son: saludo, consulta_horario, consulta_producto, crear_pedido, "
        "solicitar_factura, otro."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Mensaje: \"{user_text}\""}
    ]

    try:
        resp = openai.ChatCompletion.create(
            model=general_config['openai']['model'],
            messages=messages,
            temperature=0,
            max_tokens=10
        )
        return resp.choices[0].message.content.strip().lower()
    except Exception as e:
        _logger.error("Error detectando intención: %s", e)
        return "otro"
