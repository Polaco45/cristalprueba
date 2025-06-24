# -*- coding: utf-8 -*-
from odoo import models

class Website(models.Model):
    _inherit = 'website'

    def get_current_pricelist(self):
        """
        Devuelve la lista de precios específica de este sitio;
        si no hay, devuelve la global (sin sitio asignado).
        """
        self.ensure_one()
        Pricelist = self.env['product.pricelist']
        website_ids = [self.id]

        # 1) Intento primero obteniendo las listas asignadas EXCLUSIVAMENTE a este sitio
        pl_specific = Pricelist.search([
            ('public_website_ids', 'in', website_ids),
            ('public_website_ids', '!=', False),
        ], order='sequence asc', limit=1)
        if pl_specific:
            return pl_specific

        # 2) Si no encuentras ninguna, devuelvo la global (sin asociación de sitio)
        pl_global = Pricelist.search([
            ('public_website_ids', '=', False),
        ], order='sequence asc', limit=1)
        return pl_global

    def get_pricelist_available(self, show_visible=False, country_code=False):
        """
        Devuelve todas las listas de precios válidas para este sitio web.
        - show_visible=True: filtra solo las marcadas como 'selectable'.
        - country_code='AR': filtra por país si está configurado.
        """
        self.ensure_one()
        website_ids = [self.id]
        domain = [
            '|',
            # Listas globales
            ('public_website_ids', '=', False),
            # Listas específicamente asignadas a este sitio
            ('public_website_ids', 'in', website_ids),
        ]
        if show_visible:
            # Solo las listas habilitadas para selección en eCommerce
            domain.append(('selectable', '=', True))
        if country_code:
            # Filtrar listas sin grupo de países o que incluyan el código
            domain += ['|',
                       ('country_group_ids', '=', False),
                       ('country_group_ids.country_ids.code', '=', country_code)]
        return self.env['product.pricelist'].search(domain, order='sequence asc')
