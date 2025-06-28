from odoo import http
from odoo.http import request

class WebsiteSaleDiscount(http.Controller):
    @http.route(['/shop/payment'], type='http', auth="public", website=True)
    def shop_payment(self, **kwargs):
        order = request.website.sale_get_order()
        if order:
            discount_payment = order.payment_acquirer_id.discount_percent if order.payment_acquirer_id else 0.0
            discount_delivery = order.carrier_id.discount_percent if order.carrier_id else 0.0
            discount_total = discount_payment + discount_delivery

            for line in order.order_line:
                if line.product_id:
                    line.price_unit = line.product_id.lst_price * (1 - discount_total / 100.0)
        return request.redirect('/shop/checkout')
