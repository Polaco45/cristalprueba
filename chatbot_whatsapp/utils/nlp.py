import openai
import logging
from ..config.config import general_config

_logger = logging.getLogger(__name__)


def detect_intention(user_text, api_key):
    openai.api_key = api_key

    prompt = (
        "Eres un clasificador de intenciones para un chatbot de atención al cliente de una tienda de productos de limpieza.\n"
        "Clasifica el siguiente mensaje del usuario en una de estas categorías:\n"
        "- saludo\n- consulta_horario\n- consulta_producto\n- crear_pedido\n- solicitar_factura\n- otro\n\n"
        f"Mensaje: \"{user_text}\"\n"
        "Intención:"
    )

    try:
        result = openai.ChatCompletion.create(
            model=general_config['openai']['model'],
            messages=[
                {"role": "system", "content": "Sos un clasificador de intenciones para un chatbot de productos de limpieza."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=10
        )
        return result.choices[0].message.content.strip()

    except Exception as e:
        _logger.error("Error al detectar intención: %s", e)
        return "otro"