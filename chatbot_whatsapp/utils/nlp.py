# utils/nlp.py
import openai
import logging
from ..config.config import general_config

_logger = logging.getLogger(__name__)

def detect_intention(conversation_context, api_key):
    """Clasifica la intención del último mensaje en una conversación."""
    openai.api_key = api_key

    system_prompt = (
        "Eres un clasificador de intenciones para un chatbot de atención al cliente "
        "de una tienda de productos de limpieza. Tu tarea es analizar toda la conversación "
        "y clasificar la intención del último mensaje del usuario.\n"
        "Las categorías posibles son: saludo, consulta_horario, consulta_producto, "
        "crear_pedido, solicitar_factura, otro.\n"
        "Devuelve solo una palabra correspondiente a la categoría."
    )

    messages = [{"role": "system", "content": system_prompt}] + conversation_context

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
