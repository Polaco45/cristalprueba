from odoo import models

class Website(models.Model):
    _inherit = 'website'

    def _get_pricelist(self):
        # Buscar lista de precios asociada al sitio web actual
        return self.env['product.pricelist'].search([
            ('website_ids', 'in', self.id),
        ], limit=1)
