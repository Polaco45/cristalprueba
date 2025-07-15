# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from uuid import uuid4


class LoyaltyReward(models.Model):
    _inherit = 'loyalty.reward'

    shipping_allowed_type = fields.Selection([ 
        ('all', 'All Countries'),
        ('by_countries', 'Specific Countries')
        ],
        string='Free Shipping Eligibility',
        default="all"
        )
    shipping_allowed_countries = fields.Many2many('res.country',string='Allowed Shipping Countries')
    