from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

class WebsiteSaleExtended(WebsiteSale):

    def _apply_payment_delivery_discount(self, order):
        order_lines_to_remove = order.order_line.filtered(lambda l: l.name in [
            'Descuento por método de pago', 'Descuento por método de entrega'
        ])
        order_lines_to_remove.unlink()

        subtotal = sum(order.order_line.filtered(lambda l: not l.is_delivery).mapped('price_subtotal'))

        # Descuento por método de pago
        if order.payment_provider_id and order.payment_provider_id.discount_percent and order.payment_provider_id.discount_product_id:
            discount = -subtotal * (order.payment_provider_id.discount_percent / 100.0)
            request.env['sale.order.line'].create({
                'order_id': order.id,
                'product_id': order.payment_provider_id.discount_product_id.id,
                'name': 'Descuento por método de pago',
                'product_uom_qty': 1,
                'price_unit': discount,
            })

        # Descuento por método de entrega
        if order.carrier_id and order.carrier_id.discount_percent and order.carrier_id.discount_product_id:
            discount = -subtotal * (order.carrier_id.discount_percent / 100.0)
            request.env['sale.order.line'].create({
                'order_id': order.id,
                'product_id': order.carrier_id.discount_product_id.id,
                'name': 'Descuento por método de entrega',
                'product_uom_qty': 1,
                'price_unit': discount,
            })

    @http.route(['/shop/payment'], type='http', auth="public", website=True, sitemap=False)
    def shop_payment(self, **post):
        res = super().shop_payment(**post)
        order = request.website.sale_get_order()
        if order:
            self._apply_payment_delivery_discount(order)
        return res