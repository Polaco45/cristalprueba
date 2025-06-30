from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Un campo para acumular el total de descuento
    discount_amount = fields.Monetary(string='Total Descuento', readonly=True, store=True)

    @api.onchange('carrier_id', 'payment_provider_id', 'order_line')
    def _onchange_discounts(self):
        untaxed = self.amount_untaxed or 0.0
        disc = 0.0
        # 1) Descuento por transporte
        if self.carrier_id.discount_percent:
            disc += untaxed * (self.carrier_id.discount_percent / 100.0)
        # 2) Descuento por pago, sobre lo que queda
        if self.payment_provider_id.discount_percent:
            base = untaxed - disc
            disc += base * (self.payment_provider_id.discount_percent / 100.0)
        self.discount_amount = disc
