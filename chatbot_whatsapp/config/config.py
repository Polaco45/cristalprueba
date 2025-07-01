import yaml
import os

def load_config(file_name):
    """Carga un archivo de configuración YAML desde la ruta del módulo."""
    base_path = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(base_path, file_name)
    
    with open(config_file, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

# Cargar todas las configuraciones en diccionarios separados
general_config = load_config('config/general_config.yml')
prompts_config = load_config('config/prompts.yml')
messages_config = load_config('config/messages.yml')