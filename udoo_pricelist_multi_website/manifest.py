# -*- coding: utf-8 -*-
{
    'name': 'Pricelist Multi Website',
    'version': '18.0.1.0.0',
    'category': 'Website/Ecommerce',
    'summary': 'Allow multi-website assignment for pricelists and partner-specific pricelist',
    'license': 'OPL-1',
    'author': 'Custom',
    'depends': [
        'website_sale',
        'website',
        'product',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/product_pricelist_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
