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
from odoo import models, fields


class AccountInvoiceInherit(models.Model):
    _inherit = 'account.move'


    aff_visit_id = fields.One2many('affiliate.visit','act_invoice_id',string="Report")
    
    
    
    def action_register_payment(self):
        res = super(AccountInvoiceInherit, self).action_register_payment()
        if self.aff_visit_id:
            res['context']['aff_move_id'] = self.id
        return res




class AccountPaymentInherit(models.Model):
    _inherit = 'account.payment'
    _description = "Account Payment Inherit Model"


    def action_post(self):
        """
            Overrided the  action_post() method to modify the state of the linked affiliate commission
            to 'paid' from the affiliate invoice.
        """
        result = super(AccountPaymentInherit,self).action_post()
        if self.env.context.get('active_model') == 'account.move.line':
            aff_move_id = self._context.get('aff_move_id')
            move_id = self.env['account.move'].browse([aff_move_id]) if aff_move_id else False
            if move_id:
                if move_id.state == "posted" and move_id.aff_visit_id:
                    for visit in move_id.aff_visit_id:
                        if visit.state != "paid":
                            visit.write({"state":"paid"})
        return result
