# -*- coding: utf-8 -*-
from odoo import http
from odoo.addons.website_sale.controllers.main import WebsiteSale as WebsiteSaleOriginal

class WebsiteSale(WebsiteSaleOriginal):

    def _get_pricelist_context(self, pricelist, **kwargs):
        """
        Override to ignore any pricelist passed in, and force using 
        the one returned by Website.get_current_pricelist() for the current website.
        """
        # Force using the current website’s pricelist in session
        website = http.request.website
        pricelist = website.get_current_pricelist()
        # Call super with the pricelist we just obtained
        return super(WebsiteSale, self)._get_pricelist_context(pricelist, **kwargs)
