{
    'name': "Descuento por método de pago y entrega",
    'version': '18.0.1.0.0',
    'summary': "Aplica un descuento en función del medio de pago y método de entrega",
    'category': 'Website',
    'author': 'Tu Nombre o Empresa',
    'depends': ['payment', 'sale', 'delivery', 'website_sale'],
    'data': [
        'views/payment_acquirer_views.xml',
        'views/delivery_carrier_views.xml',
        'views/sale_order_views.xml',
    ],
    'application': True,
    'license': 'LGPL-3',
}
