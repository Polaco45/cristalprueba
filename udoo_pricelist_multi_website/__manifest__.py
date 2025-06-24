{
    'name': 'Pricelist Multi Website',
    'version': '1.0.1',
    'category': 'Website/Ecommerce',
    'summary': 'Allow multi-website assignment for product pricelists',
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
