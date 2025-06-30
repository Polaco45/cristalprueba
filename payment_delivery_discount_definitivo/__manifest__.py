{
    'name': "Descuento por método de pago y entrega",
    'version': "1.0",
    'category': 'Website',
    'summary': "Aplica descuentos por método de pago y transporte en el e-commerce",
    'depends': [
        'website_sale',
        'delivery',
        'payment',
        'sale',
    ],
    'data': [
        'views/delivery_carrier_views.xml',
        'views/payment_provider_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
