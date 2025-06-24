# -*- coding: utf-8 -*-
from odoo import api, models

class ProductPricelist(models.Model):
    _inherit = ['product.pricelist', 'multi.website.mixin']

    @api.model
    def _search_get_detail(self, website, order, options):
        """ Si public_website_ids está vacío, aparece en todos los sitios;
            si no, sólo en los sitios seleccionados. """
        res = super()._search_get_detail(website, order, options)
        # añadimos la lógica para filtrar por sitios
        res['base_domain'].append('|')
        res['base_domain'].append(('public_website_ids', '=', False))
        res['base_domain'].append(('public_website_ids', 'in', website.ids))
        return res
