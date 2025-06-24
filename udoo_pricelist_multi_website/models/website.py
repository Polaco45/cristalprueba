# -*- coding: utf-8 -*-
from odoo import models, api

class Website(models.Model):
    _inherit = 'website'

    def get_current_pricelist(self):
        self.ensure_one()
        return self.env['product.pricelist'].search(
            ['|',
             ('public_website_ids', '=', False),
             ('public_website_ids', 'in', self.id)],
            order='sequence asc',
            limit=1,
        )
