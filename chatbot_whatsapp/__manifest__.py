# chatbot_whatsapp/__manifest__.py
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
        'mail',      # <-- Correcto
        'sale',
        'account',
        'whatsapp'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_jobs.xml',
        'views/discuss_channel_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            '/static/src/js/chatbot_toggle_button.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}