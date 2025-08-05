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
from datetime import timedelta
from odoo.addons.auth_signup.models.res_partner import SignupError
import random
from ast import literal_eval
from odoo.http import request
from odoo.tools import ustr


class AffiliateRequest(models.Model):
    _name = "affiliate.request"
    _description = "Affiliate Request Model"

    def random_token(self):
    # the token has an entropy of about 120 bits (6 bits/char * 20 chars)
        chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        return ''.join(random.SystemRandom().choice(chars) for i in range(20))




    password = fields.Char(string='password', help="Password of the requested affiliate user")
    name = fields.Char(string="Email", help="Email of the requested affiliate user")
    partner_id = fields.Many2one('res.partner', string="Partner", help="Partner of the affiliate request")
    signup_token = fields.Char(string='Token', help="Signup token used during the signup of new affiliate user")
    signup_expiration = fields.Datetime(copy=False, string="Signup Expiration Time", help="Signup Expiration Time for the affiliate request")
    signup_valid = fields.Boolean(compute='_compute_signup_valid', string='Signup Token is Valid',default=False)
    signup_type = fields.Char(string='Signup Token Type', copy=False, help="Signup token type of the affiliate request i.e. 'signup'")
    user_id = fields.Many2one('res.users', help="Requested affiliate user")

    parent_aff_key = fields.Char(string='Parent Affiliate Key', help="Parent affiliate key of the requested affiliate user")
    state = fields.Selection([
        ('draft', 'Requested'),
        ('register', 'Pending For Approval'),
        ('cancel', 'Rejected'),
        ('aproove', 'Approved'),
        ], string='Status', readonly=True, default='draft', help="State of the affiliate request")


    # multiple website functionality
    website_id = fields.Many2one('website', string='Website', default=lambda self: self.env['website'].search([], limit=1).id)
    
    @api.model_create_multi
    def create(self, vals_list):
        aff_request = self
        for vals in vals_list:
            _logger.debug("these are vals we need to create aff req -->  %r", vals)
            if vals.get('user_id'):
                """ for portal users """
                if len(self.search([('user_id','=',vals.get('user_id'))])) == 0:
                    aff_request =  super(AffiliateRequest,self).create(vals)
                else:
                    aff_request = self.search([('user_id','=',vals.get('user_id'))])
            else:
                """ for new user signup with affiliate sign up page """
                aff_request =  super(AffiliateRequest,self).create(vals)
                aff_request.signup_token = self.random_token()
                aff_request.signup_expiration = fields.Datetime.now()
                aff_request.signup_type = 'signup'
                self.send_joining_mail(aff_request)

        return aff_request

    def _compute_signup_valid(self):

        """
            Method to calculate the signup valid time for the affiliate request.
            After one day sign up token validation will be false
        """
        if self.user_id:
            self.signup_valid = self.signup_valid
            pass
        else:
            dt = fields.Datetime.from_string(fields.Datetime.now())
            expiration = fields.Datetime.from_string(self.signup_expiration)+timedelta(days=1)
            if dt > expiration:
                self.signup_valid = False
            else:
                self.signup_valid = True


    def action_cancel(self):
        """
            Method to perform the reject operation for the received affiliate requests.
            Called from the 'Reject' button click on the affilate request form.
        """
        user = self.env['res.users'].search([('login','=',self.name),('active','=',True)])
        """ find id of security group user """
        user_group_id = self.env['ir.model.data'].check_object_reference('affiliate_management', 'affiliate_security_user_group')[1]
        if self.user_id:
            if self.user_id.id == self.env.ref('base.user_admin').id:
                raise UserError(_("Admin can't be an Affiliate"))
            """ for portal user remove group ids from user's groups_id """
            user.groups_id = [(3, user_group_id)]
            user.groups_id = [(3, user_group_id+1)]

            user.partner_id.is_affiliate = False
            self.state = 'cancel'
            template_id = self.env.ref('affiliate_management.reject_affiliate_email')
            user_mail = self.env.user.partner_id.company_id.email or self.env.company.email
            email_values = {"email_from":user_mail}
            db = request.session.get('db')
            mail_id = template_id.with_context({"db":db}).send_mail(self.id,force_send=True,email_values=email_values)
            current_mail = self.env['mail.mail'].sudo().browse(mail_id)
            res = current_mail.send()
        return True

    def action_aproove(self):
        """
            Method to perform the approve operation for the received affiliate requests on the basis 
            of certain conditions.
            Called from the 'Approve' button click on the affilate request form.
        """
        if self.user_id:
            if self.user_id.id == self.env.ref('base.user_admin').id:
                raise UserError(_("Admin can't be an Affiliate"))
            affiliate_program = self.env['affiliate.program'].search([("website_id",'=',self.website_id.id)])
            if not affiliate_program:
                raise UserError(_("In Configuration settings Program is absent"))
            with self.env.cr.savepoint():
                self.set_group_user(self.user_id.id)
                self.state = 'aproove'
                self.user_id.partner_id.is_affiliate = True
            self.env.cr.commit()
            template_id = self.env.ref('affiliate_management.welcome_affiliate_email')
            user_mail = self.env.user.partner_id.company_id.email or self.env.company.email
            email_values = {"email_from":user_mail}
            mail_id = template_id.send_mail(self.id,force_send=True,email_values=email_values)
            current_mail = self.env['mail.mail'].sudo().browse(mail_id)
            res = current_mail.send()
        return True




    @api.model
    def _signup_create_user(self, values):
        """ create a new user from the template user """
        IrConfigParam = self.env['ir.config_parameter']
        template_user_id = literal_eval(IrConfigParam.get_param('base.template_portal_user_id', 'False'))
        template_user = self.browse(template_user_id)
        assert template_user.exists(), _('Signup: invalid template user')

        """ check that uninvited users may sign up """
        if 'partner_id' not in values:
            if not literal_eval(IrConfigParam.get_param('auth_signup.allow_uninvited', 'False')):
                raise SignupError(_('Signup is not allowed for uninvited users'))

        assert values.get('login'), _("Signup: no login given for new user")
        assert values.get('partner_id') or values.get('name'), _("Signup: no name or partner given for new user")

        """ create a copy of the template user (attached to a specific partner_id if given) """
        values['active'] = True
        try:
            with self.env.cr.savepoint():
                return template_user.with_context(reset_password=False).copy(values)
        except Exception as e:
            """ copy may failed if asked login is not available. """
            raise SignupError(ustr(e))

    def send_joining_mail(self,aff_request):
        """
            Method to send the joining mail to the new affiliate users on the basis of valid signup.
            Called in the regenerate_token() method.
        """
        if aff_request.signup_valid:
            template_id = self.env.ref('affiliate_management.join_affiliate_email')
            user_mail = self.env.user.partner_id.company_id.email or self.env.company.email
            email_values = {"email_from":user_mail}
            mail_id = template_id.send_mail(aff_request.id,force_send=True,email_values=email_values)
            current_mail = self.env['mail.mail'].sudo().browse(mail_id)
            res = current_mail.send()
        return True


    def regenerate_token(self):
        """
            Method to regerate the signup token for the new affiliate users.
        """
        self.signup_token = self.random_token()
        self.signup_expiration = fields.Datetime.now()
        self.signup_valid = True
        self.send_joining_mail(self)


    def set_group_user(self,user_id):
        """ 
            Method to assign group to portal user after the successful signup.
        """
        UserObj = self.env['res.users'].sudo()
        user_group_id = self.env['ir.model.data']._xmlid_lookup('affiliate_management.affiliate_security_user_group')[1]
        groups_obj = self.env["res.groups"].browse(user_group_id)
        if groups_obj:
            for group_obj in groups_obj:
                group_obj.write({"users": [(4, user_id, 0)]})
                user = UserObj.browse([user_id])
                user.active = True
                user.partner_id.is_affiliate = True
                user.partner_id.res_affiliate_key = ''.join(random.choice('0123456789ABCDEFGHIJ0123456789KLMNOPQRSTUVWXYZ') for i in range(8))
                user.partner_id.affiliate_website_id = self.website_id
                

    def checkRequestExists(self,user_id):
        """
            Method to check the existing affiliate request with a specific user_id.
            Called on the affiliate website template.
        """
        exist = self.search([('user_id','=',user_id.id)])
        return len(exist) and True or False

    def checkRequeststate(self,user_id):
        """
            Method to check the state of the affiliate request with a specific user_id.
            Called on the affiliate website template.
        """
        exist = self.search([('user_id','=',user_id.id)])
        if len(exist):
            if exist.state == 'register':
                return 'pending'
            elif exist.state == 'cancel':
                return 'cancel'
