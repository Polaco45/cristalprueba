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
from odoo import http, fields
from odoo.http import request
import logging
_logger = logging.getLogger(__name__)
from odoo.addons.website_sale.controllers.main  import WebsiteSale
import datetime


class WebsiteSale(WebsiteSale):

    def create_aff_visit_entry(self,vals):
        """
            Method to create the affiliate traffic reports.
        """
        ppc_exist = self.check_ppc_exist(vals)
        if ppc_exist:
            visit = ppc_exist
        else:
            visit = request.env['affiliate.visit'].sudo().create(vals)
        return visit


    def check_ppc_exist(self,vals):
        """
            Method to check that the nique ppc is enabled in settings or not. 
            If enabled it will return the existing traffic visit otherwise return False.
        """
        domain = [('type_id','=',vals['type_id']),('affiliate_method','=',vals['affiliate_method']),('affiliate_key','=',vals['affiliate_key']),('ip_address','=',vals['ip_address'])]
        visit = request.env['affiliate.visit'].sudo().search(domain)
        check_unique_ppc = request.env['res.config.settings'].sudo().website_constant().get('unique_ppc_traffic')
        if check_unique_ppc:
            if visit:
                return visit
            else:
                return False
        else:
            return False


    @http.route([
        '/shop',
        '/shop/page/<int:page>',
        '/shop/category/<model("product.public.category"):category>',
        '/shop/category/<model("product.public.category"):category>/page/<int:page>'
    ], type='http', auth="public", website=True,sitemap=WebsiteSale.sitemap_shop)
    def shop(self, page=0, category=None, search='', min_price=0.0, max_price=0.0, ppg=False, **post):
        """ 
            Overrided the shop controller in the website_sale to add the affiliate key
            to the browser cookies if affiliate key exists in the url. 
        """
        enable_ppc = request.env['res.config.settings'].sudo().website_constant().get('enable_ppc')
        expire = False
        result = super(WebsiteSale,self).shop(page=page, category=category, search=search, min_price=min_price, max_price=max_price, ppg=ppg, **post)
        aff_key = request.httprequest.args.get('aff_key')
        if category and aff_key:
            expire = self.calc_cookie_expire_date()
            partner_id = request.env['res.partner'].sudo().search([('res_affiliate_key','=',aff_key),('is_affiliate','=',True)])
            vals = self.create_affiliate_visit(aff_key,partner_id,category)
            vals.update({'affiliate_type':'category'})
            if ( len(partner_id) == 1):
                affiliate_visit = self.create_aff_visit_entry(vals) if enable_ppc else False
                result.set_cookie(key='affkey_%s'%(aff_key), value='category_%s'%(category.id),expires=expire)
            else:
                _logger.info("=====affiliate_visit not created by category===========")
        else:
            if aff_key:
                expire = self.calc_cookie_expire_date()
                partner_id = request.env['res.partner'].sudo().search([('res_affiliate_key','=',aff_key),('is_affiliate','=',True)])
                if partner_id:
                    result.set_cookie(key='affkey_%s'%(aff_key), value='shop',expires=expire)
        return result


    def _get_additional_shop_values(self, values):
        """
            Overrided the method to set the referral link and categories in 
            the affiliate popup on the shop page  
        """
        result = super(WebsiteSale,self)._get_additional_shop_values(values)
        partner = request.env.user.partner_id
        partner_aff_program = request.env['affiliate.program'].sudo().search([('website_id', '=', request.website.id)], limit=1)
        if partner_aff_program and partner.is_affiliate and partner.res_affiliate_key :
            db = request.session.get('db')
            db = "db=%s" %(db)
            page_url = request.httprequest.url
            categories = request.env['product.public.category'].sudo().search([])
            if page_url.find('?') == -1:
                result.update({
                    'referral_link': "%s?aff_key=%s&%s" %(page_url,partner.res_affiliate_key,db),
                    'categories': categories,
                    })
            else:
                result.update({
                    'referral_link': "%s&aff_key=%s&%s#" %(page_url,partner.res_affiliate_key,db),
                    'categories': categories,
                    })

        return result
    

    def _prepare_product_values(self, product, category, search, **kwargs):
        """
            Overrided the method to set the affiliate product url in the affiliate popup 
            on the product page  
        """
        result = super(WebsiteSale,self)._prepare_product_values(product, category, search, **kwargs)
        partner = request.env.user.partner_id
        partner_aff_program = request.env['affiliate.program'].sudo().search([('website_id', '=', request.website.id)], limit=1)
        if partner_aff_program and partner.is_affiliate and partner.res_affiliate_key :
            db = request.session.get('db')
            db = "db=%s" %(db)
            page_url = request.httprequest.url
            affiliate_product_url = None
            if page_url.find('?')==-1:
                affiliate_product_url = page_url+ '?' + db + '&aff_key='+partner.res_affiliate_key
            else:
                affiliate_product_url =  page_url+ '&' + db + '&aff_key='+partner.res_affiliate_key

            result.update({
                'affiliate_product_url': affiliate_product_url,
                })
        return result


    @http.route(['/shop/<model("product.template"):product>'], type='http', auth="public", website=True, sitemap=WebsiteSale.sitemap_products)
    def product(self, product, category='', search='', **kwargs):
        """ 
            Overrided the product controller in the website_sale to add the affiliate key
            to the browser cookies if affiliate key exists in the url. 
        """
        enable_ppc = request.env['res.config.settings'].sudo().website_constant().get('enable_ppc')
        expire = self.calc_cookie_expire_date()
        result = super(WebsiteSale,self).product(product=product, category=category, search=search, **kwargs)
        if request.httprequest.args.get('aff_key'):
            # aff_key is fetch from url
            aff_key = request.httprequest.args.get('aff_key')
            partner_id = request.env['res.partner'].sudo().search([('res_affiliate_key','=',aff_key),('is_affiliate','=',True)])
            vals = self.create_affiliate_visit(aff_key,partner_id,product)
            vals.update({'affiliate_type':'product'})
            if ( len(partner_id) == 1):
                affiliate_visit = self.create_aff_visit_entry(vals) if enable_ppc else False
                # "create_aff_visit_entry " this methods check whether the visit is already created or not or if created return the no. of existing record in object
                result.set_cookie(key='affkey_%s'%(aff_key),value='product_%s'%(product.id),expires=expire)
                _logger.info("============affiliate_visit created by product==%r=======",affiliate_visit)
            else:
                _logger.info("=====affiliate_visit not created by product===========%s %s"%(aff_key,partner_id))
        return result


    @http.route(['/shop/confirmation'], type='http', auth="public", website=True, sitemap=False)
    def shop_payment_confirmation(self, **post):
        """
            Overrided the controller to update the affiliate cookies after the sale
            order confirmation
        """
        result = super(WebsiteSale,self).shop_payment_confirmation(**post)
        sale_order_id = result.qcontext.get('order')
        return self.update_affiliate_visit_cookies( sale_order_id,result )


    def create_affiliate_visit(self,aff_key,partner_id,type_id):
        """ method to create the values for the order reports and return it."""
        current_website = request.website
        aff_program = request.env['affiliate.program'].sudo().search([('website_id', '=', current_website.id)], limit=1)
        vals = {
                'affiliate_method':'ppc',
                'affiliate_key':aff_key,
                'affiliate_partner_id':partner_id.id,
                'url':request.httprequest.full_path,
                'ip_address':request.httprequest.environ['REMOTE_ADDR'],
                'type_id':type_id.id,
                'convert_date':fields.datetime.now(),
                'affiliate_program_id': aff_program.id,
                'website_id': current_website.id
            }
        return vals

    def update_affiliate_visit_cookies(self , sale_order_id ,result):
        """update affiliate.visit from cokkies data i.e created in product and shop method"""
        cookies = dict(request.httprequest.cookies)
        visit = request.env['affiliate.visit']
        arr=[]# contains cookies product_id
        sale_order_id = sale_order_id.filtered(lambda s: s.state == 'sale')
        txn = sale_order_id and sale_order_id.transaction_ids.filtered(lambda s: s.state == 'done') or False
        for k,v in cookies.items():
            if 'affkey_' in k:
                arr.append(k.split('_')[1])
        if arr and sale_order_id and txn:
            partner_id = request.env['res.partner'].sudo().search([('res_affiliate_key','=',arr[0]),('is_affiliate','=',True)])
            current_website = request.website
            aff_program = request.env['affiliate.program'].sudo().search([('website_id', '=', current_website.id)], limit=1)
            for s in sale_order_id.order_line:
                if hasattr(s, 'is_delivery') and s.is_delivery:
                    continue
                if len(arr)>0 and partner_id:
                    product_tmpl_id = s.product_id.product_tmpl_id.id
                    aff_visit = visit.sudo().create({
                        'affiliate_method':'pps',
                        'affiliate_key':arr[0],
                        'affiliate_partner_id':partner_id.id,
                        'url':"",
                        'ip_address':request.httprequest.environ['REMOTE_ADDR'],
                        'type_id':product_tmpl_id,
                        'affiliate_type': 'product',
                        'type_name':s.product_id.id,
                        'sales_order_line_id':s.id,
                        'convert_date':fields.datetime.now(),
                        'affiliate_program_id': aff_program.id,
                        'website_id': current_website.id,
                        'product_quantity' : s.product_uom_qty,
                        'is_converted':True
                    })
            # delete cookie after first sale occur
            cookie_del_status=False
            for k,v in cookies.items():
                if 'affkey_' in k:
                    cookie_del_status = result.delete_cookie(key=k)
        return result


    def calc_cookie_expire_date(self):
        """
            Method to calculate the expiry of the affiliate cookie 
        """
        ConfigValues = request.env['res.config.settings'].sudo().website_constant()
        cookie_expire = ConfigValues.get('cookie_expire')
        cookie_expire_period = ConfigValues.get('cookie_expire_period')
        time_dict = {
            'hours':cookie_expire,
            'days':cookie_expire*24,
            'months':cookie_expire*24*30,
        }
        return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=time_dict[cookie_expire_period])
