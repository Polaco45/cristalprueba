# -*- coding: utf-8 -*-
# This module and its content is copyright of Technaureus Info Solutions Pvt. Ltd. - ©
# Technaureus Info Solutions Pvt. Ltd 2024. All rights reserved.

{
    'name': 'Website Minimum Sale Price',
    'version': '18.0.1.0.5',
    'category': 'website',
    'summary': 'Manage your website minimum sale price',
    'sequence': 1,
    'price': 10,
    'currency': 'EUR',
    'author': 'Technaureus Info Solutions Pvt. Ltd.',
    'website': 'http://www.technaureus.com/',
    'license': 'LGPL-3',
    'description': """
        This app restrict purchasing products from website if the order total is below minimum sale price. 
    """,
    'depends': [
        'website_sale',
    ],
    'data': ['views/res_config_settings_views.xml',
             'views/website_sale_views.xml',
             ],
    'assets': {
        'web.assets_frontend': [
            'tis_min_sale_price/static/src/js/website_sale_new.js',
            'tis_min_sale_price/static/src/**/*',
        ],
    },
    'images': ['images/main_screenshot.png'],
    'installable': True,
    'application': True,
    'auto_install': False
}
