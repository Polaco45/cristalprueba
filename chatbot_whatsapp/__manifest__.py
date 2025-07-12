{
    'name': "Chatbot WhatsApp",
    'version': '1.0',
    'summary': "Chatbot de atención al cliente para WhatsApp usando OpenAI",
    'description': """
        Este módulo extiende el modelo whatsapp.message para analizar mensajes entrantes de WhatsApp
        y responder automáticamente según la intención detectada (OpenAI).
        Soporta: pedidos, confirmaciones, facturas y FAQs.
    """,
    'author': "Felipe Martínez",
    'website': "https://felipemartinezcv.com",
    'category': 'Tools',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'sale',
        'account',
        'whatsapp'  # Asegurate que es el nombre técnico correcto del módulo de WhatsApp
    ],
    'data': [
        'security/ir.model.access.csv',# XMLs si agregás vistas, acciones, parámetros de sistema, etc.
        'data/cron_jobs.xml',
    ],
    'assets': {
        # Si en el futuro agregás JS/CSS para interfaz
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
