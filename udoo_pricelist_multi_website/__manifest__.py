# -*- coding: utf-8 -*-
{
    'name': 'Pricelist Multi Website',
    'version': '1.0.1',
    'category': 'Website/Ecommerce',
    'summary': 'Assign pricelists to multiple websites and respect partner pricelist',
    'license': 'OPL-1',
    'author': 'Custom',
    'website': 'https://tu-dominio.com',
    'depends': [
        'website_sale',
        'product',
        'website',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/product_pricelist_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
