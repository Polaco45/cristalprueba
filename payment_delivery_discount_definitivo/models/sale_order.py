from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # --- 1) Campos nuevos ---
    # Para guardar el método de pago elegido en la web
    payment_provider_id = fields.Many2one(
        'payment.provider',
        string='Método de pago',
        help='Proveedor de pago elegido en la tienda'
    )
    # Total del descuento calculado
    discount_amount = fields.Monetary(
        string='Total Descuento',
        readonly=True,
        store=True,
    )

    # --- 2) Lógica de recálculo ---
    @api.onchange('carrier_id', 'payment_provider_id', 'order_line')
    def _onchange_discounts(self):
        """Recalcula discount_amount según %
           de carrier y de payment provider."""
        untaxed = self.amount_untaxed or 0.0
        disc = 0.0

        # 1) Descuento por transportista
        if self.carrier_id.discount_percent:
            disc += untaxed * (self.carrier_id.discount_percent / 100.0)

        # 2) Descuento por método de pago (sobre lo que queda)
        if self.payment_provider_id.discount_percent:
            base = untaxed - disc
            disc += base * (self.payment_provider_id.discount_percent / 100.0)

        self.discount_amount = disc
