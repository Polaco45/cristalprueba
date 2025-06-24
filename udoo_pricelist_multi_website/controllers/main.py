# -*- coding: utf-8 -*-
from odoo import http
from odoo.addons.website_sale.controllers.main import WebsiteSale as WebsiteSaleBase

class WebsiteSale(WebsiteSaleBase):

    def _get_pricelist_context(self, pricelist, **kwargs):
        """
        1) Si el usuario tiene partner.property_product_pricelist, úsala.
        2) Sino, llama al método original (que respetará website → global).
        """
        # 1) Chequeo partner
        partner = http.request.env.user.partner_id
        if partner and partner.property_product_pricelist:
            return {
                'pricelist': partner.property_product_pricelist,
                # puedes añadir otras claves de contexto si las usas
            }

        # 2) Caigo al nativo para respetar website → global
        return super()._get_pricelist_context(pricelist, **kwargs)
