# -*- coding: utf-8 -*-
{
    'name': 'Pricelist Multi Website',
    'version': '1.0.1',
    'category': 'Website/Ecommerce',
    'summary': 'Allow multi-website assignment for product pricelists and partner-specific pricelist',
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
    # Auto-carga nuestros modelos (no controllers)
    'application': False,
    'installable': True,
    'auto_install': False,
}
