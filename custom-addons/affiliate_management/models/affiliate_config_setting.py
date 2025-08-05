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
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AffiliateConfiguration(models.TransientModel):

    _inherit = 'res.config.settings'
    _description = "Affiliate Configuration Model"

    @api.model
    def _get_program(self):
        """
            Method to get the default affiliate program
        """
        return self.env['affiliate.program'].sudo().search([("is_default_program","=",True)], limit=1).id


    @api.model
    def _get_banner(self):
        """
            Method to get the list of affiliate banners
        """
        return self.env['affiliate.banner'].sudo().search([],limit=1).id

    affiliate_program_id = fields.Many2one('affiliate.program',string="Affiliate Program", help="Default Affiliate Program")
    enable_ppc = fields.Boolean(string= "Enable PPC", default=True, help="If enabled, the PPC commssions will be provided to the affiliates otherwise only PPS commissions will be provided.")
    auto_approve_request = fields.Boolean(default=False, string="Auto Approve Request", help="Marking this field to True will automatically approve the affiliate request")
    ppc_maturity = fields.Integer(string="PPC Maturity",required=True, default=1, help="Time Interval of the cron that will provide PPC commission to the affiliates.")
    ppc_maturity_period = fields.Selection([('days','Days'),('months','Months'),('weeks','Weeks')],required=True,default='days', help="Time Period of the cron that will provide PPC commission to the affiliates.")
    cookie_expire = fields.Integer(string="Cookie expiration",required=True, default=1, help="Cookie Expiry Time")
    cookie_expire_period = fields.Selection([('hours','Hours'),('days','Days'),('months','Months')],required=True,default='days',help="Cookie Expiry Period")
    payment_day = fields.Integer(string="Payment day",required=True, default=7, help="Payment Day for the confirmed affiliate commissions")
    minimum_amt = fields.Integer(string="Minimum Payout Balance",required=True, default=0, help="Minimum Payout Balance for the confirmed affiliate commissions")
    currency_id = fields.Many2one('res.currency', 'Currency', required=True,
        default=lambda self: self.env.user.company_id.currency_id.id, help="Currency set in the current company")
    aff_product_id = fields.Many2one('product.product', 'Affiliate Product',help="Product used in Invoicing")
    enable_signup = fields.Boolean(string= "Enable Sign Up", default=True, help="Enabling this will enable the signup from the affiliate website")
    enable_login = fields.Boolean(string= "Enable Log In", default=True, help="Enabling this will enable the login from the affiliate website")
    enable_forget_pwd = fields.Boolean(string= "Enable Forget Password", default=False, help="Enabling this will enable frorgetting the password from the affiliate website")
    affiliate_banner_id = fields.Many2one('affiliate.banner',string="Banner", help="Affiliate that will be visible on the affiliate website")
    welcome_mail_template = fields.Many2one('mail.template',string="Approved Request Mail",readonly=True, help="Mail Template for the approved affiliate request")
    reject_mail_template = fields.Many2one('mail.template',string="Reject Request Mail ",readonly=True, help="Mail Template for the rejected affiliate request")
    Invitation_mail_template = fields.Many2one('mail.template',string="Invitation Request Mail ",readonly=True, help="Mail template for the affiliate joining request")
    unique_ppc_traffic = fields.Boolean(string= "Unique ppc for product", default=False, help="This field is used to enable unique traffic on product for an Affiliate for a specific browser.")
    term_condition = fields.Html(string="Term & condition Text", related='affiliate_program_id.term_condition',translate=True)
    work_title = fields.Text(string="How Does It Work Title",related='affiliate_program_id.work_title', translate=True)
    work_text = fields.Html(string="How Does It Work Text",related='affiliate_program_id.work_text', translate=True)
    auto_confirm_visit = fields.Boolean(string= "Automatic Confirm Visits", default=False, help="If enabled, it will automatically confirm affiliate visits which are in draft state.")



    def set_values(self):
        if self.minimum_amt < 1:
            raise UserError(_("Minimum Payout Balance should not be in negative figure."))
        super(AffiliateConfiguration, self).set_values()
        IrDefault = self.env['ir.default'].sudo()
        IrDefault.set('res.config.settings', 'ppc_maturity', self.ppc_maturity)
        IrDefault.set('res.config.settings', 'ppc_maturity_period', self.ppc_maturity_period)
        IrDefault.set('res.config.settings', 'enable_ppc', self.enable_ppc)
        IrDefault.set('res.config.settings', 'auto_approve_request', self.auto_approve_request )
        IrDefault.set('res.config.settings', 'aff_product_id', self.aff_product_id.id)
        IrDefault.set('res.config.settings', 'enable_signup', self.enable_signup )
        IrDefault.set('res.config.settings', 'enable_login', self.enable_login )
        IrDefault.set('res.config.settings', 'enable_forget_pwd', self.enable_forget_pwd )
        IrDefault.set('res.config.settings', 'payment_day', self.payment_day)
        IrDefault.set('res.config.settings', 'minimum_amt', self.minimum_amt)
        IrDefault.set('res.config.settings', 'cookie_expire', self.cookie_expire)
        IrDefault.set('res.config.settings', 'cookie_expire_period', self.cookie_expire_period)
        IrDefault.set('res.config.settings', 'unique_ppc_traffic', self.unique_ppc_traffic)

        IrDefault.set('res.config.settings', 'term_condition', self.term_condition)
        IrDefault.set('res.config.settings', 'work_title', self.work_title)
        IrDefault.set('res.config.settings', 'work_text', self.work_text)
        IrDefault.set('res.config.settings', 'auto_confirm_visit', self.auto_confirm_visit)


        IrDefault.set('res.config.settings', 'affiliate_program_id', self._get_program())
        IrDefault.set('res.config.settings', 'affiliate_banner_id', self._get_banner())
        self.scheduler_ppc_maturity_set()

    def scheduler_ppc_maturity_set(self):
        ppc_maturity_schedular = self.env.ref("affiliate_management.affiliate_ppc_maturity_scheduler_call")
        ppc_maturity_schedular.write({
        'interval_number' : self.ppc_maturity,
        'interval_type' : self.ppc_maturity_period,
        })


    @api.model
    def get_values(self):
        template_1 = self.env['ir.model.data']._xmlid_lookup('affiliate_management.welcome_affiliate_email')[1]
        template_2 = self.env['ir.model.data']._xmlid_lookup('affiliate_management.reject_affiliate_email')[1]
        template_3 = self.env['ir.model.data']._xmlid_lookup('affiliate_management.join_affiliate_email')[1]
        res = super(AffiliateConfiguration, self).get_values()
        IrDefault = self.env['ir.default'].sudo()
        res.update(
            welcome_mail_template=IrDefault._get('res.config.settings', 'welcome_mail_template') or template_1,
            reject_mail_template=IrDefault._get('res.config.settings', 'reject_mail_template') or template_2,
            Invitation_mail_template=IrDefault._get('res.config.settings', 'Invitation_mail_template') or template_3,
            work_title=IrDefault._get('res.config.settings', 'work_title') or _("The process is very simple. Simply, signup/login to your affiliate portal, pick your affiliate link and place them into your website/blogs and watch your account balance grow as your visitors become our customers, as :"),
            work_text=IrDefault._get('res.config.settings', 'work_text') or _("<ol><li><p style='text-align: left; margin-left: 3em;'>Visitor clicks on affiliate links posted on your website/blogs.</p></li><li><p style='text-align: left; margin-left: 3em;'>A cookie is placed in their browser for tracking purposes. The visitor browses our site and may decide to order.</p></li><li><p style='text-align: left; margin-left: 3em;'>The visitor browses our site and may decide to order. If the visitor orders, the order will be registered as a sale for you and you will receive a commission for this sale.</p></li><li><p style='text-align: left; margin-left: 3em;'>If the visitor orders, the order will be registered as a sale for you and you will receive a commission for this sale.</p></li></ol>"),
            unique_ppc_traffic=IrDefault._get('res.config.settings', 'unique_ppc_traffic') or False,
            term_condition=IrDefault._get('res.config.settings', 'term_condition') or _("Write your own Term and Condition"),
            ppc_maturity  =IrDefault._get('res.config.settings', 'ppc_maturity') or 1,
            ppc_maturity_period=IrDefault._get('res.config.settings', 'ppc_maturity_period')or 'months',
            enable_ppc =IrDefault._get('res.config.settings', 'enable_ppc') or False,
            auto_approve_request =IrDefault._get('res.config.settings', 'auto_approve_request' ) or False,
            aff_product_id=IrDefault._get('res.config.settings', 'aff_product_id') or False,
            enable_signup =IrDefault._get('res.config.settings', 'enable_signup') or False,
            enable_login =IrDefault._get('res.config.settings', 'enable_login' ) or False,
            enable_forget_pwd =IrDefault._get('res.config.settings', 'enable_forget_pwd') or False,
            payment_day =IrDefault._get('res.config.settings', 'payment_day') or 7,
            minimum_amt =IrDefault._get('res.config.settings', 'minimum_amt') or 1,
            cookie_expire=IrDefault._get('res.config.settings', 'cookie_expire') or 1,
            cookie_expire_period =IrDefault._get('res.config.settings', 'cookie_expire_period') or 'days',
            affiliate_program_id =IrDefault._get('res.config.settings', 'affiliate_program_id') or self._get_program(),
            affiliate_banner_id =IrDefault._get('res.config.settings', 'affiliate_banner_id') or self._get_banner(),
            auto_confirm_visit =IrDefault._get('res.config.settings', 'auto_confirm_visit') or False,
            )
        return res

    def website_constant(self, website=None):
        res ={}
        IrDefault = self.env['ir.default'].sudo()
        if website:
            aff_prgmObj = self.env['affiliate.program'].search([('website_id', '=', website.id)], limit=1)
        else:
            aff_prgmObj = self.env['affiliate.program'].search([("is_default_program", "=", True)], limit=1)
        
        res.update(
            work_title = aff_prgmObj.work_title or "The process is very simple. Simply, signup/login to your affiliate portal, pick your affiliate link and place them into your website/blogs and watch your account balance grow as your visitors become our customers, as :",
            work_text = aff_prgmObj.work_text or  "<ol><li><p style='text-align: left; margin-left: 3em;'>Visitor clicks on affiliate links posted on your website/blogs.</p></li><li><p style='text-align: left; margin-left: 3em;'>A cookie is placed in their browser for tracking purposes.</p></li><li><p style='text-align: left; margin-left: 3em;'>The visitor browses our site and may decide to order. </p></li><li><p style='text-align: left; margin-left: 3em;'>If the visitor orders, the order will be registered as a sale for you and you will receive a commission for this sale.</p></li></ol>",
            unique_ppc_traffic = IrDefault._get('res.config.settings', 'unique_ppc_traffic') or False,
            term_condition = aff_prgmObj.term_condition or "Write your own Term and Condition",
            enable_ppc =IrDefault._get('res.config.settings', 'enable_ppc') or False,
            enable_signup =IrDefault._get('res.config.settings', 'enable_signup') or False,
            enable_login =IrDefault._get('res.config.settings', 'enable_login' ) or False,
            enable_forget_pwd =IrDefault._get('res.config.settings', 'enable_forget_pwd') or False,
            auto_approve_request =IrDefault._get('res.config.settings', 'auto_approve_request' ) or False,
            cookie_expire=IrDefault._get('res.config.settings', 'cookie_expire') or 1,
            cookie_expire_period =IrDefault._get('res.config.settings', 'cookie_expire_period') or 'days',
            payment_day =IrDefault._get('res.config.settings', 'payment_day') or 7,
            minimum_amt =IrDefault._get('res.config.settings', 'minimum_amt') or 1,
            aff_product_id=IrDefault._get('res.config.settings', 'aff_product_id') or False,
            auto_confirm_visit=IrDefault._get('res.config.settings', 'auto_confirm_visit') or False,
            )
        return res


    def open_program(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'My Affiliate Programs',
            'view_mode': 'list,form',
            'res_model': 'affiliate.program',
            'target': 'current',
        }


    def open_banner(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'My Affiliate Banner',
            'view_mode': 'form',
            'res_model': 'affiliate.banner',
            'res_id': self.affiliate_banner_id.id,
            'target': 'current',
        }
