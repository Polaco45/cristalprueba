# -*- coding: utf-8 -*-

from odoo import models, fields, api

class LoyaltyCustomerTier(models.Model):
    _name = 'loyalty.customer.tier'
    _description = 'Loyalty Customer Tier'

    _sql_constraints = [
    ('name_uniq', 'UNIQUE (name)', 'You can not have two Loyalty Customer Tier with the same name !')
    ]

    name = fields.Char('Group Name', required=True)
    description = fields.Text('Description')
    customer_count = fields.Integer(string="Customer Count", compute='_get_customer_count')
    
    def action_view_linked_partners(self):
        # Open the res.partner records linked to this loyalty tier
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Customers',
            'res_model': 'res.partner',
            'view_mode': 'list',
            'domain': [('loyalty_customer_tier_id', '=', self.id)],
            'context': {},
        }
        return action
    
    def _get_customer_count(self):
        for rec in self:
            rec.customer_count = self.env['res.partner'].search_count([('loyalty_customer_tier_id', '=', self.id)])