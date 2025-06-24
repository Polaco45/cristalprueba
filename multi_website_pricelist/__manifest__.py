# __manifest__.py

{
    'name': 'Multi Website Pricelist',
    'version': '1.0',
    'author': 'ChatGPT',
    'website': 'https://your-domain.com',
    'summary': 'Permite asignar una misma lista de precios a múltiples sitios web',
    'description': 'Este módulo convierte el campo de sitio web en la lista de precios a Many2many y ajusta la lógica para Odoo.sh.',
    'category': 'Website',
    'depends': ['website_sale', 'product'],
    'data': [
        'views/product_pricelist_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
