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
import datetime
from dateutil.relativedelta import relativedelta

class AffiliateVisit(models.Model):
    _name = "affiliate.visit"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"
    _description = "Affiliate Visit"

    name = fields.Char(string = "Name",readonly=True)


    @api.depends('affiliate_type','type_id')
    def _calc_type_name(self):
        for record in self:
            if record.affiliate_type == 'product':
                record.type_name = record.env['product.template'].browse([record.type_id]).name
            if record.affiliate_type == 'category':
                record.type_name = record.env['product.public.category'].browse([record.type_id]).name


    affiliate_method = fields.Selection([("ppc","Pay Per Click"),("pps","Pay Per Sale")],string="Order Report",readonly=True,help="state of traffic either ppc or pps")
    affiliate_type = fields.Selection([("product","Product"),("category","Category")],string="Affiliate Type",readonly=True,help="whether the ppc or pps is on product or category")
    type_id = fields.Integer(string='Type Id',readonly=True,help="Id of product template on which ppc or pps traffic create")
    type_name = fields.Char(string='Type Name',readonly=True,compute='_calc_type_name',help="Name of the product")
    is_converted = fields.Boolean(string="Is Converted",readonly=True,)
    sales_order_line_id = fields.Many2one("sale.order.line",readonly=True,)
    affiliate_key = fields.Char(string="Key",readonly=True,)
    affiliate_partner_id = fields.Many2one("res.partner",string="Affiliate",readonly=True,)
    url = fields.Char(string="Url",readonly=True,)
    ip_address = fields.Char(readonly=True,)
    currency_id = fields.Many2one('res.currency', 'Currency', required=True,
        default=lambda self: self.env.user.company_id.currency_id.id,readonly=True,)
    convert_date = fields.Datetime(string='Date',readonly=True,)
    price_total = fields.Monetary(string="Sale value",related='sales_order_line_id.price_total',help="Total sale value of product" )
    unit_price = fields.Float(string="Product Unit Price", related='sales_order_line_id.price_unit', readonly=True,help="price unit of the product")
    commission_amt = fields.Float(readonly=True, help="The commission amount for this affiliate visit")
    affiliate_program_id = fields.Many2one('affiliate.program',string='Program',readonly=True, help="Affiliate Program from which the commission will calculated for this affiliate visit")
    amt_type = fields.Char(string='Commission Matrix',readonly=True,help="Commission Matrix on which commission value calculated")
    act_invoice_id = fields.Many2one("account.move", string='Act Invoice id',readonly=True, help="Invoice for the provided affiliate commission")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('cancel', 'Cancel'),
        ('confirm', 'Confirm'),
        ('invoice', 'Invoiced'),
        ('paid', 'Paid'),
        ], string='Status', readonly=True, default='draft', tracking=True )
    product_quantity = fields.Integer(readonly=True, help="Purchased Product Quantity for the affiliate visit" )

    website_id = fields.Many2one('website', string='Website', related="affiliate_program_id.website_id")



    @api.model_create_multi
    def create(self, vals_list):
        """
            Overrided the Method to set the name of the affiliate visit as per the sequence code
        """
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('affiliate.visit')
        return super(AffiliateVisit,self).create(vals_list)


    def action_cancel(self):
        """
            Method to updated the state of the affiliate visit report to 'Cancel'
        """
        self.state = 'cancel'
        return True


    def action_confirm(self, is_auto=False):
        """
            Method to updated the state of the affiliate visit report to 'Confirm' based on certain conditions
        """
        check_enable_ppc = self.env['res.config.settings'].sudo().website_constant().get('enable_ppc')

        if self.affiliate_method != 'ppc' and not self.sales_order_line_id:
            if not is_auto:
                raise UserError(_("Order is not present in visit {}.").format(self.name))
            else:
                self.message_post(body=_("Order is not present in visit {}.").format(self.name), subject="Sale Order doesn't exists")
                return False
        if self.affiliate_method != 'ppc' and not self.price_total:
            if not is_auto:
                raise UserError(_("Sale value must be greater than zero."))
            else:
                self.message_post(body=_("Sale value must be greater than zero."), subject="Sale Value Error")
                return False
        if self.affiliate_method == 'ppc' and (not check_enable_ppc) :
            if not is_auto:
                raise UserError(_("Pay per click is disabled, so you can't confirm it's commission"))
            else:
                self.message_post(body=_("Pay per click is disabled, so you can't confirm it's commission."), subject="Pay Per Click Error")
                return False
        self.state = 'confirm'
        status = self._get_rate(self.affiliate_method , self.affiliate_type, self.type_id )
        if status.get('is_error'):
            if not is_auto:
                raise UserError(_('{}').format(status['message']))
            else:
                self.message_post(body=_('{}').format(status['message']), subject="Commission Rate Error")
                return False
        return True



    def action_paid(self):
        """
            Method to updated the state of the affiliate visit report to 'Paid'
        """
        self.state = 'paid'
        return True



    # scheduler according to the scheduler define in data automated scheduler

    @api.model
    def process_scheduler_queue(self):
        """
            Method called from the automated schedular cron to update the state of the confirmed affiliate visists
            and create the invoices for those affiliates. 
        """
        users_all = self.env['res.users'].search([('is_affiliate','=',True)])
        ConfigValues = self.env['res.config.settings'].sudo().website_constant()
        payment_day = ConfigValues.get('payment_day')
        threshold_amt = ConfigValues.get('minimum_amt')
        # make the date of current month of setting date
        payment_date = datetime.date(datetime.date.today().year, datetime.date.today().month, payment_day)
        for u in users_all:
            visits = self.search([('state','=','confirm'),('affiliate_partner_id','=',u.partner_id.id)])
            if payment_date and visits:
                visits = visits.filtered(lambda r: fields.Date.from_string(r.create_date) <= payment_date)
                _logger.debug("*****filter- visits=%r******",visits)

            _logger.debug("****before******before method***visits**%r*******",visits)
            visits = self.check_enable_ppc_visits(visits)
            _logger.debug("*****after*****after method***visits**%r*******",visits)
            total_comm_per_user = 0
            if visits:
                for v in visits:
                    total_comm_per_user = total_comm_per_user + v.commission_amt
                if total_comm_per_user >= threshold_amt and payment_date:
                    dic={
                        'name':_("Total earn commission on ppc and pps"),
                        'quantity':1,
                        'price_unit':total_comm_per_user,
                        'product_id':ConfigValues.get('aff_product_id'),
                    }
                    invoice_dict = [
                        {
                            'invoice_line_ids': [(0, 0, dic)],
                            'move_type': 'in_invoice',
                            'partner_id':u.partner_id.id,
                            'invoice_date':fields.Datetime.now().date()
                        }
                    ]

                    inv_id = self.env['account.move'].create(invoice_dict)
                    for v in visits:
                        v.state = 'invoice'
                        v.act_invoice_id = inv_id.id
        return True

    
    @api.model
    def process_automatic_confirmation(self):
        IrDefault = self.env['ir.default'].sudo()
        auto_confirm_visit =IrDefault._get('res.config.settings', 'auto_confirm_visit')
        if auto_confirm_visit:
            users_all = self.env['res.users'].search([('is_affiliate','=',True)])
            for u in users_all:
                aff_visits = self.search([('state','=','draft'),('affiliate_partner_id','=',u.partner_id.id)])
                for visit in aff_visits:
                    visit.action_confirm(is_auto=True)
        
        return True


    def check_enable_ppc_visits(self,visits):
        """
            Method to check the PPC commission is enabled in the affiliate settings.
            If enabled then will return all the visits else will return only 'PPS' type visits. 
        """
        
        check_enable_ppc = self.env['res.config.settings'].sudo().website_constant().get('enable_ppc')
        if check_enable_ppc:
            return visits
        else:
            visits = visits.filtered(lambda v: v.affiliate_method == 'pps')
            return visits



    # method call from server action
    @api.model
    def create_invoice(self):
        """
            Method to create the invoice of the confirmed affiliate visit report and updated the state to 'Invoiced'.
        """
        # get the value of enable ppc from settings
        ConfigValues = self.env['res.config.settings'].sudo().website_constant()
        check_enable_ppc = ConfigValues.get('enable_ppc')
        aff_vst = self._context.get('active_ids')
        act_invoice = self.env['account.move']
        # check the first visit of context is ppc or pps and enable pps
        affiliate_method_type = self.browse([aff_vst[0]]).affiliate_method
        if affiliate_method_type == 'ppc' and (not check_enable_ppc) :
            raise UserError(_("Pay per click is disabled, so you can't generate it's invoice"))

        invoice_ids =[]
        for v in aff_vst:
            vst = self.browse([v])
            if vst.state == 'confirm':
                # ********** creating invoice line *********************
                if vst.sales_order_line_id:
                    dic={
                            'name':"Type "+vst.affiliate_type+" on Pay Per Sale ",
                            'quantity':1,
                            'price_unit':vst.commission_amt,
                            'product_id':ConfigValues.get('aff_product_id'),
                        }
                else:
                    dic={
                            'name':"Type "+vst.affiliate_type+" on Pay Per Click ",
                            'price_unit':vst.commission_amt,
                            'quantity':1,
                            'product_id':ConfigValues.get('aff_product_id'),
                        }

                invoice_dict = [
                                {
                                    'invoice_line_ids': [(0, 0, dic)],
                                    'move_type': 'in_invoice',
                                    'partner_id':vst.affiliate_partner_id.id,
                                    'invoice_date':fields.Datetime.now().date()
                                }]
                line = act_invoice.create(invoice_dict)
                vst.state = 'invoice'
                vst.act_invoice_id = line.id
                invoice_ids.append(line)
        msg = _('{} records has been invoiced out of {}').format(str(len(invoice_ids)), str(len(aff_vst)))


        partial_id = self.env['wk.wizard.message'].create({'text': msg})
        return {
        'name': "Message",
        'view_mode': 'form',
        'view_id': False,
        'res_model': 'wk.wizard.message',
        'res_id': partial_id.id,
        'type': 'ir.actions.act_window',
        'target': 'new',
        }


    def _get_rate(self,affiliate_method,affiliate_type,type_id):
        
        '''
            Method to compute commission amount for the confirmed affiliate visits based on affiliate program 
            and commission type
            Arguments: (pps,product,product_id) or (ppc,product,product_id) or (ppc,category,category_id)
        '''
        product_exists = False
        category_exists = False
        commission = 0.0
        commission_type = False
        adv_commission_amount = 0.0
        from_currency = self.sales_order_line_id.currency_id
        company = self.env.user.company_id
        response = {}
        if self.affiliate_program_id:
            ''' check product.id in product.template '''
            if affiliate_type == 'product':
                product_exists = self.env['product.template'].browse([type_id])
            
            ''' check category.id in product.public.category '''
            if affiliate_type == 'category':
                category_exists = self.env['product.public.category'].browse([type_id])

            ''' pay per click '''
            if affiliate_method == 'ppc' and product_exists or category_exists: # pay per click
                commission = from_currency._convert(self.affiliate_program_id.amount_ppc_fixed,self.affiliate_program_id.currency_id, company, fields.Date.today())
                commission_type = 'fixed'
                self.commission_amt = commission
            else:
                ''' pay per sale '''
                if affiliate_method == 'pps' and product_exists :
                    ''' for pps_type simple '''
                    if self.affiliate_program_id.pps_type == 's':
                        if self.affiliate_program_id.matrix_type == 'f':  # fixed
                            amt  = from_currency._convert(self.affiliate_program_id.amount,self.affiliate_program_id.currency_id, company, fields.Date.today())
                            commission =  amt * self.product_quantity
                            commission_type = 'fixed'
                        else:
                            if self.affiliate_program_id.matrix_type == 'p' and (not self.affiliate_program_id.amount >100): # percentage
                                amt_product = from_currency._convert(self.price_total,self.affiliate_program_id.currency_id, company, fields.Date.today())
                                commission = (amt_product * self.affiliate_program_id.amount/100)
                                commission_type = 'percentage'
                            else:
                                response={
                                        'is_error':1,
                                        'message':_('Percentage amount is greater than 100'),
                                }
                    else:
                        ''' for pps type advance (advance depends upon price list) '''

                        if self.affiliate_program_id.pps_type == 'a' and product_exists:
                            _logger.debug('================pps type advance calculation===============')
                            adv_commission_amount,commission,commission_type = self.advance_pps_type_calc()
                            ''' adv_commission_amount = is a amount if advance commission
                                commission = is a amount which is earned by commission '''
                            commission = commission * self.product_quantity
                            if commission and commission_type:
                                _logger.debug("---22----adv_commission_amount--%r--commission_value-%r--------commission_value_type-%r------",adv_commission_amount,commission,commission_type)

                            else:
                                response={
                                    'is_error':1,
                                    'message':_('No commission Category Found for this product..')
                                }


                        else:
                            response={
                                    'is_error':1,
                                    'message':_('pps_type is advance'),
                            }

                else:
                    response={
                            'is_error':1,
                            'message':_('Affiliate method is neither ppc nor pps or affiliate type is absent(product or category)'),
                    }
        else:

            response={
                    'is_error':1,
                    'message':_('Program is absent in visit'),
            }

        if commission:
            self.commission_amt = commission
            if commission_type == 'fixed' and affiliate_method == 'ppc':
                self.amt_type   =  self.affiliate_program_id.currency_id.symbol+ str(commission)
            if commission_type == 'percentage' and affiliate_method == 'ppc':
                self.amt_type =   str(self.affiliate_program_id.amount_ppc_fixed)+ '%'
            ''' for pps '''
            if commission_type == 'percentage' and self.affiliate_program_id.pps_type == 's':
                self.amt_type = str(self.affiliate_program_id.amount) +"%"
            if commission_type == 'fixed' and affiliate_method == 'pps' and self.affiliate_program_id.pps_type == 's':
                self.amt_type =    self.affiliate_program_id.currency_id.symbol + str(commission)
            if commission_type == 'fixed' and affiliate_method == 'pps' and self.affiliate_program_id.pps_type == 'a':
                self.amt_type =   self.affiliate_program_id.currency_id.symbol + str(adv_commission_amount)+" advance"
            if commission_type == 'percentage' and affiliate_method == 'pps' and self.affiliate_program_id.pps_type == 'a':
                self.amt_type =   str(adv_commission_amount)+"%"+" advance"
            response={
                    'is_error':0,
                    'message':_('Commission successfully added'),
                    'comm_type':commission_type,
                    'comm_amt' : commission
            }

        else:
            if response.get('is_error') == 1:
                response={
                        'is_error':1,
                        'message':_('{}').format(response.get('message')),
                }

        return response



    def advance_pps_type_calc(self):
        adv_commission_amount,commision_value,commision_value_type = self.env["advance.commision"].calc_commision_adv(self.affiliate_program_id.advance_commision_id.id, self.type_id , self.price_total)
        _logger.debug("---11----adv_commision_amount----commision_value-%r--------commision_value_type-%r------",adv_commission_amount,commision_value,commision_value_type)
        return adv_commission_amount,commision_value,commision_value_type




    @api.model
    def process_ppc_maturity_scheduler_queue(self):
        """
            Method to confirm the draft PPC visits that will be called from the scheduled action 
            on specific time period. 
        """
        _logger.debug("-----Inside----process_ppc_maturity_scheduler_queue-----------")
        check_enable_ppc = self.env['res.config.settings'].sudo().website_constant().get('enable_ppc')
        all_ppc_visits = self.search([('affiliate_method','=','ppc'),('state','=','draft')])
        if check_enable_ppc:
            for visit in all_ppc_visits:
                visit.action_confirm()

    @api.model
    def get_traffic_daily_stats(self, website_id):
        '''
            Method to get Traffic and Order report stats for an affiliate for last 7 days
        '''
        day_label, count_traffic, count_order = [], [], []
        partner_visits = self.search([('affiliate_partner_id', '=', self.env.user.partner_id.id), ('state', 'not in', ['draft', 'cancel']), ('website_id', '=', website_id)])
        ppc_convert_datetimes = partner_visits.filtered(lambda v: v.affiliate_method=='ppc').mapped('create_date')
        pps_convert_datetimes = partner_visits.filtered(lambda v: v.affiliate_method=='pps').mapped('create_date')
        ppc_convert_dates = [cd.strftime("%d/%m/%Y") for cd in ppc_convert_datetimes if cd]
        pps_convert_dates = [cd.strftime("%d/%m/%Y") for cd in pps_convert_datetimes if cd]
        for i in range(7):
            vst_date = datetime.datetime.now() - timedelta(i)
            day_label.append(vst_date.strftime("%d %b"))
            count_traffic.append(ppc_convert_dates.count(vst_date.strftime("%d/%m/%Y")) if vst_date.strftime("%d/%m/%Y") in ppc_convert_dates else 0)
            count_order.append(pps_convert_dates.count(vst_date.strftime("%d/%m/%Y")) if vst_date.strftime("%d/%m/%Y") in pps_convert_dates else 0)
        
        return {"day_label": day_label[::-1], "count_traffic": count_traffic[::-1], "count_order": count_order[::-1]}
    
    
    @api.model
    def get_traffic_monthly_stats(self, website_id):
        '''
            Method to get Traffic and Order report stats for an affiliate for last 12 months
        '''
        month_label, count_traffic, count_order = [], [], []
        partner_visits = self.search([('affiliate_partner_id', '=', self.env.user.partner_id.id), ('state', 'not in', ['draft', 'cancel']), ('website_id', '=', website_id)])
        ppc_convert_datetimes = partner_visits.filtered(lambda v: v.affiliate_method=='ppc').mapped('create_date')
        pps_convert_datetimes = partner_visits.filtered(lambda v: v.affiliate_method=='pps').mapped('create_date')
        ppc_convert_dates = [cd.strftime("%m/%Y") for cd in ppc_convert_datetimes if cd]
        pps_convert_dates = [cd.strftime("%m/%Y") for cd in pps_convert_datetimes if cd]
        for i in range(12):
            vst_date = datetime.datetime.now() - relativedelta(months=i)
            month_label.append(vst_date.strftime("%b"))
            count_traffic.append(ppc_convert_dates.count(vst_date.strftime("%m/%Y")) if vst_date.strftime("%m/%Y") in ppc_convert_dates else 0)
            count_order.append(pps_convert_dates.count(vst_date.strftime("%m/%Y")) if vst_date.strftime("%m/%Y") in pps_convert_dates else 0)
        
        return {"month_label": month_label[::-1], "count_traffic": count_traffic[::-1], "count_order": count_order[::-1]}

    
    def show_affiliate_invoice(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Affiliate Invoice',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('aff_visit_id','=', self.id)],
            'target': 'current',
        }
