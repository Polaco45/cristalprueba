# -*- coding: utf-8 -*-
from odoo import api, models

class Website(models.Model):
    _inherit = 'website'

    def get_current_pricelist(self):
        """Devuelve la lista de precios específica de este sitio;
           si no hay, devuelve la global."""
        self.ensure_one()
        website_ids = [self.id]

        Pricelist = self.env['product.pricelist']

        # 1) BUSCO SOLO listas que tengan este website_id, EXCLUYENDO las globales.
        pl_specific = Pricelist.search(
            [('public_website_ids', 'in', website_ids),
             ('public_website_ids', '!=', False)],
            order='sequence asc',
            limit=1
        )
        if pl_specific:
            return pl_specific

        # 2) Si no hay ninguna específica, uso la global (sin sitio asignado)
        pl_global = Pricelist.search(
            [('public_website_ids', '=', False)],
            order='sequence asc',
            limit=1
        )
        return pl_global

    def get_pricelist_available(self, show_visible=False, country_code=False):
        """Devuelve todas las listas válidas para este sitio."""
        self.ensure_one()
        website_ids = [self.id]
        domain = ['|',
            # o global...
            ('public_website_ids', '=', False),
            # o específicamente para este sitio
            ('public_website_ids', 'in', website_ids),
        ]
        if show_visible:
            domain.append(('selectable', '=', True))
        if country_code:
            domain += ['|',
                       ('country_group_ids', '=', False),
                       ('country_group_ids.country_ids.code', '=', country_code)]
        return self.env['product.pricelist'].search(domain, order='sequence asc')
