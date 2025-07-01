import openai
import logging
from ..config.config import general_config

_logger = logging.getLogger(__name__)

def detect_intention(conversation_history, api_key, system_prompt):
    """Clasifica la intención del último mensaje considerando el historial y un prompt de sistema específico."""
    openai.api_key = api_key

    system_message = {"role": "system", "content": system_prompt}
    messages = [system_message] + conversation_history

    _logger.info("🧠 Prompt de clasificación enviado a OpenAI:\n%s", messages)

    try:
        resp = openai.ChatCompletion.create(
            model=general_config['openai']['model'],
            messages=messages,
            temperature=0,
            max_tokens=20  # Aumentado ligeramente para nombres de intención más largos
        )
        return resp.choices[0].message.content.strip().lower().replace('"', '').replace("'", "")
    except Exception as e:
        _logger.error("❌ Error detectando intención: %s", e)
        return "otro"