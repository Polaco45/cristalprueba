# -*- coding: utf-8 -*-
from odoo import api, models

class Website(models.Model):
    _inherit = 'website'

    def get_current_pricelist(self):
        """Return the default pricelist for the current website (or global default if none specified)."""
        self.ensure_one()
        # First, try to find a pricelist explicitly for this website (or global) ordered by sequence
        pricelist = self.env['product.pricelist'].search(
            [('public_website_ids', 'in', self.id)],
            order='sequence asc',
            limit=1
        )
        if pricelist:
            return pricelist
        # If no site-specific pricelist found, fall back to a global pricelist (no website assigned)
        return self.env['product.pricelist'].search(
            [('public_website_ids', '=', False)],
            order='sequence asc',
            limit=1
        )

    def get_pricelist_available(self, show_visible=False, country_code=False):
        """
        Return the list of pricelists that can be used on this website for the current user.
        - If show_visible is True, only include pricelists marked as selectable (visible) on the website.
        - If country_code is given, only include pricelists allowed for that country (or with no country restriction).
        """
        self.ensure_one()
        # Base domain: pricelists either not tied to any website or tied to this website
        domain = ['|', ('public_website_ids', '=', False), ('public_website_ids', 'in', self.id)]
        # Only active pricelists by default (Odoo usually filters out inactive via context)
        if show_visible:
            # Filter by the 'selectable' flag for website visibility (eCommerce pricelist dropdown):contentReference[oaicite:2]{index=2}
            domain.append(('selectable', '=', True))
        if country_code:
            # Filter by country: include pricelists with no country group or with a group containing the country
            domain_country = ['|', ('country_group_ids', '=', False),
                                   ('country_group_ids.country_ids.code', '=', country_code)]
            domain = domain + domain_country  # combine domain conditions
        # Search pricelists matching the criteria, ordered by sequence (priority)
        return self.env['product.pricelist'].search(domain)
