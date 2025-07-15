# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    loyalty_customer_tier_id = fields.Many2one('loyalty.customer.tier', string="Loyalty Customer Tier")

