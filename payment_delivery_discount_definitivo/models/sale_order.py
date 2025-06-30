from odoo import models, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.onchange('carrier_id', 'payment_method_id')
    def _onchange_discount_methods(self):
        for order in self:
            disc = 0.0
            # Descuento por carrier
            if order.carrier_id.discount_percent:
                disc += order.carrier_id.discount_percent
            # Descuento por método de pago
            if order.payment_method_id.discount_percent:
                disc += order.payment_method_id.discount_percent
            order.discount_delivery_payment = disc
