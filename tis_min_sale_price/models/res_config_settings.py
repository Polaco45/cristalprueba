# -*- coding: utf-8 -*-
# This module and its content is copyright of Technaureus Info Solutions Pvt. Ltd.
# - © Technaureus Info Solutions Pvt. Ltd 2024. All rights reserved.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """inherited res.config.settings and added min_sale_price and tax_type for website sale"""
    _inherit = 'res.config.settings'

    min_sale_price = fields.Float(string='Minimum Sale Price', related='website_id.min_sale_price', readonly=False)
    tax_type = fields.Selection([
        ('tax_included', 'Tax Included'),
        ('tax_excluded', 'Tax Excluded')], string="Tax Type", related='website_id.tax_type', readonly=False)

    website_id = fields.Many2one('website', string='Website', default=lambda self: self.env['website'].get_current_website())
