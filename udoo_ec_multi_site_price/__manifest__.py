# -*- coding: utf-8 -*-
{
    'name': 'Multi-Website en Listas de Precios',
    'version': '1.0.0',
    'category': 'Website/Website',
    'summary': 'Asigna múltiples sitios web a tus listas de precios',
    'author': 'Tu Nombre o Empresa',
    'license': 'OPL-1',
    'depends': [
        'website_sale',
        'product',
        'website',
    ],
    'data': [
        'views/product_pricelist_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
