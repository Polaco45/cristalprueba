# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    # nuevo campo M2M para asignar múltiples sitios web
    public_website_ids = fields.Many2many(
        comodel_name='website',
        relation='product_pricelist_public_website_rel',
        column1='pricelist_id',
        column2='website_id',
        string='Websites',
    )

    @api.model
    def _search_get_detail(self, website, order, options):
        """
        Cuando se filtran productos de e-commerce:
         - si public_website_ids está vacío → aparece en TODOS los sitios
         - si no → sólo en los sitios marcados
        """
        res = super()._search_get_detail(website, order, options)
        # agregamos al dominio: (public_website_ids IS FALSE) OR (public_website_ids IN sitio_actual)
        res['base_domain'].append('|')
        res['base_domain'].append(('public_website_ids', '=', False))
        res['base_domain'].append(('public_website_ids', 'in', website.ids))
        return res
