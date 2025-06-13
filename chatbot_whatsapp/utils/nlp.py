import openai
import logging
from ..config.config import general_config

_logger = logging.getLogger(__name__)

def detect_intention_with_context(messages, api_key):
    """
    messages: lista de dicts tipo [{'role': 'user'|'assistant', 'content': 'texto'}, ...]
    Construye prompt para clasificación de intención con contexto completo.
    """
    openai.api_key = api_key

    # Mensaje sistema fijo, define rol
    system_msg = {
        "role": "system",
        "content": "Sos un clasificador de intenciones para un chatbot de productos de limpieza."
    }

    # Agregamos prompt explícito para clasificación al final
    user_prompt = (
        "Clasifica la intención del último mensaje en una de estas categorías:\n"
        "- saludo\n- consulta_horario\n- consulta_producto\n- crear_pedido\n- solicitar_factura\n- otro\n\n"
        "Solo responde la categoría."
    )
    # Construimos mensajes para OpenAI: sistema + contexto + prompt
    chat_messages = [system_msg] + messages + [{"role": "user", "content": user_prompt}]

    try:
        result = openai.ChatCompletion.create(
            model=general_config['openai']['model'],
            messages=chat_messages,
            temperature=0,
            max_tokens=10
        )
        return result.choices[0].message.content.strip().lower()
    except Exception as e:
        _logger.error("Error al detectar intención: %s", e)
        return "otro"
