import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class Website(models.Model):
    _inherit = 'website'

    @api.model
    def get_current_pricelist(self):
        _logger.info("🔎 [multi_website_pricelist] get_current_pricelist override llamado para website %s", self.id)
        pricelist = self.env['product.pricelist'].search(
            [('website_ids', 'in', self.id)], limit=1
        )
        if pricelist:
            _logger.info("✔️ Lista encontrada: %s", pricelist.name)
            return pricelist
        default = super(Website, self).get_current_pricelist()
        _logger.info("↩️ Fallback a lista estándar: %s", default.name)
        return default
