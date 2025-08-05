# -*- coding: utf-8 -*-
#################################################################################
# Author : Webkul Software Pvt. Ltd. (<https://webkul.com/>:wink:
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>;
#################################################################################
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import UserError
from odoo import models, fields,api,_
from odoo.http import request
import random, string
import datetime
class ResPartnerInherit(models.Model):

    _inherit = 'res.partner'

    is_affiliate = fields.Boolean(default=False, help="Field to check that the partner is affilate or not")
    res_affiliate_key = fields.Char(string="Affiliate key", help="Affiliate Key for the affiliate partner")
    pending_amt = fields.Float(compute='_compute_pending_amt', string='Pending Amount', help="Pending Amount for the affiliate partner")
    approved_amt = fields.Float(compute='_compute_approved_amt', string='Approved Amount', help="Approved Amount for the affiliate partner")
    affiliate_website_id = fields.Many2one('website', string='Affiliate Website')



    def toggle_active(self):
        for o in self:
            if o.is_affiliate:
                o.is_affiliate = False
            else:
                o.is_affiliate = True
        return super(ResPartnerInherit,self).toggle_active()

    def _compute_pending_amt(self):
        for s in self:
            visits = None
            if hasattr(request, "website"):
                visits = s.env['affiliate.visit'].search([('state','in',['confirm','invoice']),('affiliate_partner_id','=',s.id), ('website_id', '=', request.website.id)])
            else:
                visits = s.env['affiliate.visit'].search([('state','in',['confirm','invoice']),('affiliate_partner_id','=',s.id)])
            amt = 0
            if visits:
                for v in visits:
                    amt = amt + v.commission_amt
            s.pending_amt = round(amt, 2)

    def _compute_approved_amt(self):
        for s in self:
            visits = None
            if hasattr(request, "website"):
                visits = s.env['affiliate.visit'].search([('state','=','paid'),('affiliate_partner_id','=',s.id), ('website_id', '=', request.website.id)])
            else:
                visits = s.env['affiliate.visit'].search([('state','=','paid'),('affiliate_partner_id','=',s.id)])
                
            amt = 0
            if visits:
                for v in visits:
                    amt = amt + v.commission_amt
            s.approved_amt = round(amt, 2)

    def generate_key(self):
        if self.is_affiliate:
            ran = ''.join(random.choice('0123456789ABCDEFGHIJ0123456789KLMNOPQRSTUVWXYZ') for i in range(8))
            self.res_affiliate_key = ran
        else:
            raise UserError(_("Cannot generate affiliate key for non-affiliate users."))

    def write(self,vals):
        if vals.get('is_affiliate') != None and vals.get('is_affiliate') == False:
            vals.update({
                'res_affiliate_key': None
            })
        return super(ResPartnerInherit,self).write(vals)

    
    def show_affiliate_visits(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Visits',
            'res_model': 'affiliate.visit',
            'view_mode': 'list,form',
            'domain': [('affiliate_partner_id','=', self.id)],
            'target': 'current',
        }
