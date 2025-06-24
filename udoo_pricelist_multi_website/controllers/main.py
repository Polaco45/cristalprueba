# -*- coding: utf-8 -*-
from odoo import http
from odoo.addons.website_sale.controllers.main import WebsiteSale as WebsiteSaleOriginal

class WebsiteSale(WebsiteSaleOriginal):

    def _get_pricelist_context(self, pricelist, **kwargs):
        """
        Sobrescribimos para ignorar el pricelist que venga y forzar a usar
        el que devuelve Website.get_current_pricelist()
        """
        # Forzar a usar el get_current_pricelist de la web en sesión
        website = http.request.website
        pricelist = website.get_current_pricelist()
        # Llamamos al super con el pricelist que acabamos de obtener
        return super(WebsiteSale, self)._get_pricelist_context(pricelist, **kwargs)
