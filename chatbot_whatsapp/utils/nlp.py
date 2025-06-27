import openai
import logging
from ..config.config import general_config

_logger = logging.getLogger(__name__)

def detect_intention(conversation_history, api_key):
    """Clasifica la intención del último mensaje considerando el historial."""
    openai.api_key = api_key

    system_message = {
        "role": "system",
        "content": (
            "Eres un clasificador de intenciones para un chatbot de atención al cliente "
            "de una tienda de productos de limpieza.\n"
            "Debes predecir la intención del último mensaje del usuario en función de la conversación completa.\n"
            "Ten en cuenta tanto los mensajes del usuario como las respuestas del asistente.\n"
            "Categorías posibles: saludo, consulta_horario, consulta_producto, crear_pedido, "
            "solicitar_factura, otro.\n"
            "Devolvé únicamente la categoría (en minúsculas, sin explicaciones).\n"
        )
    }

    messages = [system_message] + conversation_history

    # 📋 Log completo del prompt
    _logger.info("🧠 Prompt de clasificación enviado a OpenAI:\n%s", messages)

    try:
        resp = openai.ChatCompletion.create(
            model=general_config['openai']['model'],
            messages=messages,
            temperature=0,
            max_tokens=10
        )
        return resp.choices[0].message.content.strip().lower()
    except Exception as e:
        _logger.error("❌ Error detectando intención: %s", e)
        return "otro"
