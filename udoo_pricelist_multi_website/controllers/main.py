import logging
from odoo import http
from odoo.addons.website_sale.controllers.main import WebsiteSale as WebsiteSaleBase

_logger = logging.getLogger(__name__)

class WebsiteSale(WebsiteSaleBase):

    def _get_pricelist_context(self, pricelist=None, **kwargs):
        # DEBUG: registrar usuario, lista de precios del partner y lista original
        partner = http.request.env.user.partner_id
        _logger.debug("OVERRIDE _get_pricelist_context called: user=%s partner_pricelist=%s orig_pricelist=%s",
                      http.request.env.user.login,
                      getattr(partner, 'property_product_pricelist', False),
                      pricelist.name if pricelist else None)
        # 1) Si el usuario está logueado (partner distinto del público) y tiene una lista asignada, usarla
        if partner and http.request.env.user != http.request.website.user_id and partner.property_product_pricelist:
            _logger.debug(" → Forzando pricelist desde partner: %s", partner.property_product_pricelist.name)
            pricelist_context = dict(http.request.env.context)
            pricelist_context.update({
                'pricelist': partner.property_product_pricelist.id,
                'partner': partner.id
            })
            return pricelist_context, partner.property_product_pricelist
        # 2) En caso contrario, invocar al super para la lógica por defecto
        pl_context, pl_pricelist = super(WebsiteSale, self)._get_pricelist_context(pricelist=pricelist, **kwargs)
        _logger.debug(" → Caída al super, se usará: %s", pl_pricelist.name if pl_pricelist else None)
        return pl_context, pl_pricelist
