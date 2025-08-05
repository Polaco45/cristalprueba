
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
class AffiliateProgram(models.Model):
    _name = "affiliate.program"
    _description = "Affiliate Model"

    name = fields.Char(string = "Name",required=True, help="Name of the Affiliate Program")
    ppc_type = fields.Selection([("s","Simple"),("a","Advance")], string="Ppc Type",required=True,default="s", help="Type of the PPC commission for this Affiliate Program")
    amount_ppc_fixed = fields.Float(string="Amount Fixed",default=0,required=True, help="Fixed Commission Amount of the PPC for this Affiliate Program")
    pps_type = fields.Selection([("s","Simple"),("a","Advanced")], string="Pps Type",required=True,default="s", help="Type of the PPS commission for this Affiliate Program")
    matrix_type = fields.Selection([("f","Fixed"),("p","Percentage")],required=True,default='f',string="Matrix Type", help="Matrix Type for the Simple type of the PPS commission for this Affiliate Program")
    amount = fields.Float(string="Amount",default=0, required=True, help="Fixed/Percentage amount of the Simple PPS commission for this Affiliate Program")
    currency_id = fields.Many2one('res.currency', 'Currency',
        default=lambda self: self.env.user.company_id.currency_id.id)
    advance_commision_id = fields.Many2one('advance.commision',string="Pricelist",domain="[('active_adv_comsn', '=', True)]", help="Advance Affiliate Commission of the PPS commission for this Affiliate Program")

    # config field for translation
    term_condition = fields.Html(string="Term & condition Text", translate=True, help="Terms and Conditions of this Affiliate Program")
    work_title = fields.Text(string="How Does It Work Title", translate=True, help="Title for the How Does It Work section of this Affiliate Program for the affiliate Website")
    work_text = fields.Html(string="How Does It Work Text", translate=True, help="Description Text for the How Does It Work section of this Affiliate Program for the affiliate Website")

    # multiple affiliate program 
    is_default_program = fields.Boolean(string="Default Affiliate Program", default=False)
    is_active = fields.Boolean(string="Active", default=True)
    
    # multiple website functionality
    website_id = fields.Many2one('website', string='Website', help="Select a website form the list of websites", default=lambda self: self.env['website'].search([], limit=1).id)
    

    def unlink(self):
        """
            Overrided the unlink() method to restrict the deletion of the default affiliate program 
        """
        if self.is_default_program:
            raise UserError(_("You can't delete the Default Affiliate Program."))
        else:
            return super(AffiliateProgram,self).unlink()

        
    @api.constrains('website_id')
    def check_website_id(self):
        program_count = self.sudo().search_count([('website_id', '=', self.website_id.id), ('id', '!=', self.id)])
        if program_count > 0:
            raise UserError("One website can be assigned to only one affiliate program. Please choose another website!")


    def write(self,vals):
        if vals.get('work_text') and vals.get('work_text')=='<p><br></p>':
            vals['work_text'] = None
        if vals.get('term_condition') and vals.get('term_condition')=='<p><br></p>':
            vals['term_condition'] = None
        
        return super(AffiliateProgram, self).write(vals)


    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        cxt = dict(self._context)
        cxt['hide_ppc'] = not self.env['ir.default'].get('res.config.settings', 'enable_ppc')

        res = super(AffiliateProgram, self.with_context(cxt)).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        return res

    @api.onchange('matrix_type')
    def check_amount(self):
        m_type = self.matrix_type
        amount = self.amount
        if m_type == 'p' and amount > 100:
            self.amount = 0

    def write(self, vals):
        if vals.get('work_text') and vals.get('work_text')=='<p><br></p>':
            vals['work_text'] = None
        if vals.get('term_condition') and vals.get('term_condition')=='<p><br></p>':
            vals['term_condition'] = None
        return super(AffiliateProgram, self).write(vals)
