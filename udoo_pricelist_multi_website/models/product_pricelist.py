# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    public_website_ids = fields.Many2many(
        comodel_name='website',
        relation='product_pricelist_public_website_rel',
        column1='pricelist_id',
        column2='website_id',
        string='Websites',
        help='Select websites where this pricelist applies. If empty, applies to all.'
    )

    @api.model
    def _search_get_detail(self, website, order, options):
        res = super(ProductPricelist, self)._search_get_detail(website, order, options)
        res['base_domain'].append('|')
        res['base_domain'].append(('public_website_ids', '=', False))
        res['base_domain'].append(('public_website_ids', 'in', website.ids))
        return res
