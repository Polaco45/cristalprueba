{
    "name": "Payment and Delivery Discount",
    "version": "18.0.1.0.0",
    "category": "Website",
    "summary": "Apply automatic discounts based on payment and delivery method",
    "depends": ["sale", "website_sale", "payment", "delivery"],
    "data": [
        "views/sale_order_views.xml",
        "views/payment_acquirer_views.xml",
        "views/delivery_carrier_views.xml"
    ],
    "installable": True,
}
