# -*- coding: utf-8 -*-
from odoo import api, models

class Website(models.Model):
    _inherit = 'website'

    def get_current_pricelist(self):
        """Devuelve la lista de precios para este sitio; si no hay específica, devuelve la global."""
        self.ensure_one()
        Pricelist = self.env['product.pricelist']
        website_ids = [self.id]
        # 1) Buscar una lista de precios específica de este sitio (no global)
        pl_specific = Pricelist.search([
            ('public_website_ids', 'in', website_ids),
            ('public_website_ids', '!=', False),
        ], order='sequence asc', limit=1)
        if pl_specific:
            return pl_specific
        # 2) Si no hay específica, devolver la primera lista global
        return Pricelist.search([('public_website_ids', '=', False)], order='sequence asc', limit=1)

    def get_pricelist_available(self, show_visible=False, country_code=False):
        """Devuelve todas las listas de precios válidas para este sitio web."""
        self.ensure_one()
        Pricelist = self.env['product.pricelist']
        domain = ['|',
                  ('public_website_ids', '=', False),
                  ('public_website_ids', 'in', [self.id])]
        if show_visible:
            domain.append(('selectable', '=', True))
        if country_code:
            domain += ['|',
                       ('country_group_ids', '=', False),
                       ('country_group_ids.country_ids.code', '=', country_code)]
        return Pricelist.search(domain, order='sequence asc')
