import yaml
import os

class Config:
    def __init__(self, relative_path):
        base_path = os.path.dirname(os.path.abspath(__file__))  # Ruta del archivo config.py
        config_file = os.path.join(base_path, '..', relative_path)  # Ruta relativa al módulo
        config_file = os.path.abspath(config_file)
        
        with open(config_file, 'r') as file:
            self.config = yaml.safe_load(file)


general_responses = Config('config/general_config.yml').config