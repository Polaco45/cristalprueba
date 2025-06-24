# -*- coding: utf-8 -*-
from odoo import models

class Website(models.Model):
    _inherit = 'website'

    def get_current_pricelist(self):
        """ Sobrescribimos para usar public_website_ids en lugar de website_id """
        self.ensure_one()
        return self.env['product.pricelist'].search(
            ['|',
             ('public_website_ids', '=', False),
             ('public_website_ids', 'in', self.id)],
            order='sequence asc',
            limit=1
        )
