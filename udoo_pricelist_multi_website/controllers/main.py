import logging
from odoo import http
from odoo.addons.website_sale.controllers.main import WebsiteSale as WebsiteSaleBase

_logger = logging.getLogger(__name__)

class WebsiteSale(WebsiteSaleBase):

    def _get_pricelist_context(self, pricelist, **kwargs):
        # 0) DEBUG: qué partner y qué lista llega originalmente
        partner = http.request.env.user.partner_id
        _logger.debug("OVERRIDE _get_pricelist_context called: "
                      "user=%s partner_pricelist=%s orig_pricelist=%s",
                      http.request.env.user.login,
                      getattr(partner, 'property_product_pricelist', False),
                      pricelist.name if pricelist else None)

        # 1) Si el partner tiene pricelist, úsala
        if partner and partner.property_product_pricelist:
            _logger.debug(" → Forzando pricelist desde partner: %s", partner.property_product_pricelist.name)
            return {'pricelist': partner.property_product_pricelist}

        # 2) Sino, caigo al super
        ctx = super(WebsiteSale, self)._get_pricelist_context(pricelist, **kwargs)
        _logger.debug(" → Caída al super, se usará: %s", ctx.get('pricelist').name)
        return ctx
