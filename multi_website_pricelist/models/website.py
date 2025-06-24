from odoo import models, api

class Website(models.Model):
    _inherit = 'website'

    @api.model
    def get_current_pricelist(self):
        # Si estamos en el frontend con request.website, entramos para ese registro
        website = self.env['website'].browse(self.env['ir.config_parameter'].sudo().get_param('website.id', default=False)) \
                  or (self if self._name == 'website' else None)
        if website:
            # Buscamos la primera lista que tenga este sitio en website_ids
            pricelist = self.env['product.pricelist'].search([
                ('website_ids', 'in', website.id),
            ], limit=1)
            if pricelist:
                return pricelist
        # Si no encontramos, delegamos a la implementación estándar
        return super(Website, self).get_current_pricelist()
