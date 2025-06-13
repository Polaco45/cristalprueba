# crilimp_lista_precios_mensual/__manifest__.py
{
    'name': 'Lista de precios mensual automático',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Sube, revisa o baja listas de precios según volumen de ventas mensual con tolerancia',
    'depends': [
        'base',
        'sale',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_listas.xml',
    ],
    'installable': True,
    'auto_install': False,
}
