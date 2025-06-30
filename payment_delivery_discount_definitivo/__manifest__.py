# __manifest__.py
{
    'name': "Descuento por método de pago y entrega",
    'version': "1.0",
    'category': "Website",
    'summary': "Aplica descuentos por método de pago y transporte en el e-commerce",
    'depends': [
        'sale',              # para sale.order
        'delivery',          # para delivery.carrier.form
        'payment',           # para payment.provider.form
        'website_sale',      # si luego extiendes algo en la web
        'website_sale_collect',  # para la vista de “In-store Delivery Carrier Form”
    ],
    'data': [
        'views/delivery_carrier_views.xml',
        'views/payment_provider_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
