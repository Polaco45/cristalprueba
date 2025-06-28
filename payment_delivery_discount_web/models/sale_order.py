from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    discount_payment = fields.Float("Descuento por método de pago (%)", readonly=True)
    discount_delivery = fields.Float("Descuento por método de entrega (%)", readonly=True)

    @api.onchange('payment_acquirer_id', 'carrier_id')
    def _compute_discount_by_method(self):
        discount_payment = self.payment_acquirer_id.discount_percent if self.payment_acquirer_id else 0.0
        discount_delivery = self.carrier_id.discount_percent if self.carrier_id else 0.0

        self.discount_payment = discount_payment
        self.discount_delivery = discount_delivery

        discount_total = discount_payment + discount_delivery
        for line in self.order_line:
            if line.product_id:
                line.price_unit = line.product_id.lst_price * (1 - discount_total / 100.0)
