# -*- coding: utf-8 -*-
from odoo import api, models

class Website(models.Model):
    _inherit = 'website'

    def get_current_pricelist(self):
        """Devuelve la pricelist para este sitio, o la global si no hay."""
        self.ensure_one()
        Pricelist = self.env['product.pricelist']
        website_ids = [self.id]

        # 1) Busco específica (no globales)
        pl_spec = Pricelist.search(
            [
                ('public_website_ids', 'in', website_ids),
                ('public_website_ids', '!=', False),
            ],
            order='sequence asc', limit=1
        )
        if pl_spec:
            return pl_spec

        # 2) Si no hay, devuelvo global
        return Pricelist.search(
            [('public_website_ids', '=', False)],
            order='sequence asc', limit=1
        )

    def get_pricelist_available(self, show_visible=False, country_code=False):
        """Devuelve todas las listas válidas para este sitio."""
        self.ensure_one()
        Pricelist = self.env['product.pricelist']
        domain = ['|',
            ('public_website_ids', '=', False),
            ('public_website_ids', 'in', [self.id]),
        ]
        if show_visible:
            domain.append(('selectable', '=', True))
        if country_code:
            domain += ['|',
                       ('country_group_ids', '=', False),
                       ('country_group_ids.country_ids.code', '=', country_code)]
        return Pricelist.search(domain, order='sequence asc')
        
