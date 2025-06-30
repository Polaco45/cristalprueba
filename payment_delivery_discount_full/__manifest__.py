{
    'name': 'Payment and Delivery Discount on Website',
    'version': '18.0.1.0.1',
    'category': 'Website',
    'summary': 'Applies discounts on website checkout by payment and delivery method',
    'author': 'Custom',
    'depends': ['website_sale', 'sale_management', 'delivery', 'payment'],
    'data': [
        'views/payment_provider_views.xml',
        'views/delivery_carrier_views.xml'
    ],
    'installable': True,
    'application': False,
}