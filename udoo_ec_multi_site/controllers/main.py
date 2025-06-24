# -*- coding: utf-8 -*-
# Copyright 2024 Sveltware Solutions

from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class MultiWebsiteSale(WebsiteSale):
    def _get_additional_shop_values(self, values):
        """
        Limit only the specified websites can see eCommerce category.

        Ref#1: odoo/addons/website_sale/controllers/main.py
            Trace line: 273 -> 420 -> 468 -> 486
        Ref#2: odoo/addons/website_sale/views/templates.xml
            Trace line: 323 - 372 -> 645 -> 830
        """
        vals = super()._get_additional_shop_values(values)
        website = request.env['website'].get_current_website()
        vals.update(
            {
                'categories': values['categories'].filtered(
                    lambda o: not o.public_website_ids or website in o.public_website_ids
                )
            }
        )
        return vals
