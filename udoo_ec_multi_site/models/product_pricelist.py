# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    # Campo M2M para asignar múltiples sitios web
    public_website_ids = fields.Many2many(
        string='Websites',
        comodel_name='website',
        relation='product_pricelist_public_website_rel',
        column1='pricelist_id',
        column2='website_id',
    )

    @api.model
    def _search_get_detail(self, website, order, options):
        """ Si public_website_ids está vacío, aparece en todos los sitios;
            si no, sólo en los sitios seleccionados. """
        res = super()._search_get_detail(website, order, options)
        res['base_domain'].append('|')
        res['base_domain'].append(('public_website_ids', '=', False))
        res['base_domain'].append(('public_website_ids', 'in', website.ids))
        return res
