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
        'mail',    
        'conversations',
        'sale',
        'account',
        'whatsapp'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_jobs.xml',
    ],
    'assets': {
        # for everything in the mail/thread/discuss view:
        'web.assets_backend': [
            'chatbot_whatsapp/static/src/js/chatbot_toggle_button.js',
            # 'chatbot_whatsapp/static/src/xml/discuss_header_extend.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}