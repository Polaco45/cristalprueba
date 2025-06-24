from odoo import models, fields

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    website_ids = fields.Many2many(
        'website',
        'pricelist_website_rel',
        'pricelist_id',
        'website_id',
        string='Sitios Web',
        help='Permite asignar esta lista de precios a múltiples sitios web.'
    )
