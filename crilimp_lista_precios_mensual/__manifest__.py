{
    'name': 'Lista de precios mensual automático',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Sube a Institutional en cuanto supere 200k y democión con tolerancia al mes siguiente',
    'license': 'LGPL-3',
    'depends': ['base', 'sale', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_listas.xml',
    ],
    'installable': True,
    'auto_install': False,
}
