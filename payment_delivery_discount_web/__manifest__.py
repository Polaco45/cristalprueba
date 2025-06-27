{
    "name": "Payment and Delivery Discount - Web",
    "version": "18.0.1.0.1",
    "category": "Website",
    "summary": "Apply discounts on payment and delivery method in website checkout",
    "depends": ["sale", "website_sale", "payment", "delivery"],
    "data": [
        "views/sale_order_views.xml",
        "views/payment_acquirer_views.xml",
        "views/delivery_carrier_views.xml"
    ],
    "installable": True,
    "assets": {
        "web.assets_frontend": [
            "/payment_delivery_discount_web/static/src/js/discount.js"
        ]
    }
}
