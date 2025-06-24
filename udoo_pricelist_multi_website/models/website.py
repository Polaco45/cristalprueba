# -*- coding: utf-8 -*-
from odoo import api, models

class Website(models.Model):
    _inherit = 'website'

    def get_current_pricelist(self):
        """Devuelve la lista de precios predeterminada para este sitio web, o la global si no hay específica."""
        self.ensure_one()
        website_ids = [self.id]  # <-- convertimos el ID en lista

        # 1) Intentar primero encontrar una lista específica del sitio
        pricelist = self.env['product.pricelist'].search(
            [('public_website_ids', 'in', website_ids)],
            order='sequence asc',
            limit=1
        )
        if pricelist:
            return pricelist

        # 2) Si no hay, volver a la lista global (public_website_ids = False)
        return self.env['product.pricelist'].search(
            [('public_website_ids', '=', False)],
            order='sequence asc',
            limit=1
        )

    def get_pricelist_available(self, show_visible=False, country_code=False):
        """
        Devuelve todas las listas de precios aplicables a este sitio web.
        - show_visible: si es True, sólo las marcadas como 'selectable' (visibles en eCommerce).
        - country_code: filtra por país (sólo listas sin restricción de país o que incluyan ese código).
        """
        self.ensure_one()
        website_ids = [self.id]  # <-- siempre lista

        # Dominio base: globales o asignadas a este sitio
        domain = ['|', ('public_website_ids', '=', False), ('public_website_ids', 'in', website_ids)]

        # Si sólo queremos las visibles (desplegable web), agregamos 'selectable'
        if show_visible:
            domain += [('selectable', '=', True)]

        # Filtro opcional por país
        if country_code:
            domain += ['|',
                       ('country_group_ids', '=', False),
                       ('country_group_ids.country_ids.code', '=', country_code)]

        # Devolvemos ordenadas por 'sequence' (prioridad)
        return self.env['product.pricelist'].search(domain, order='sequence asc')
