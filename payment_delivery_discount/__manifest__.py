# -*- coding: utf-8 -*-
{
    'name': 'Payment and Delivery Discount on Website',
    'version': '18.0.1.0.0',
    'category': 'Website',
    'summary': 'Applies discounts based on payment and delivery method in website checkout',
    'description': 'This module applies configurable discounts based on the selected payment method and delivery method during website checkout.',
    'author': 'Custom',
    'depends': ['website_sale', 'sale_management', 'delivery', 'payment'],
    'data': [
        'views/payment_provider_views.xml',
        'views/delivery_carrier_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
}
