# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.http import request

_logger = logging.getLogger(__name__)

class Website(models.Model):
    _inherit = 'website'

    @api.model
    def get_current_pricelist(self):
        """
        Override global: si el partner logeado tiene pricelist asignada,
        úsala. Sino, la específica del sitio, o finalmente la global.
        """
        # 1) Quiero el partner de la sesión (si está logeado)
        partner = request.env.user.partner_id
        pl_partner = partner.property_product_pricelist
        if pl_partner:
            _logger.info("→ Partner LOGEADO %s usa pricelist %s",
                         request.env.user.login, pl_partner.name)
            return pl_partner

        # 2) No logeado o sin pricelist: busco la lista del sitio
        site = self.env['website'].browse(request.website.id)
        # Dominios: o global (sin sitio) o explícita para este sitio
        domain = ['|',
                  ('public_website_ids', '=', False),
                  ('public_website_ids', 'in', site.id)]
        pl_site = self.env['product.pricelist'].search(
            domain, order='sequence asc', limit=1)
        _logger.info("→ DEFAULT sitio %s devuelve pricelist %s",
                     site.name, pl_site.name)
        return pl_site
