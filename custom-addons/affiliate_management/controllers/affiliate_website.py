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
from ast import literal_eval
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo import http, _
from odoo.http import request
from odoo import tools
import logging
_logger = logging.getLogger(__name__)
from odoo.addons.website_sale.controllers.main   import TableCompute
import requests
import datetime
from odoo.addons.web.controllers.utils import ensure_db, _get_login_redirect_url
from odoo.addons.affiliate_management.controllers.home import Home



class website_affiliate(Home):


    @http.route('/affiliate/', auth='public',type='http', website=True, sitemap=False)
    def affiliate(self, **kw):
        """
            Controller to visit the homepage of the affiliate website
        """
        banner = request.env['affiliate.banner'].sudo().search([])
        banner_title = banner[-1].banner_title if banner else ''
        banner_image = banner[-1].banner_image if banner else ''
        ConfigValues = request.env['res.config.settings'].sudo().website_constant(request.website)
        enable_forget_pwd = ConfigValues.get('enable_forget_pwd')
        enable_login = ConfigValues.get('enable_login')
        enable_signup = ConfigValues.get('enable_signup')
        how_it_work_title = ConfigValues.get('work_title')
        how_it_work_text = tools.html_sanitize(ConfigValues.get('work_text'))
        values = {
            'default_header':False,
            'affiliate_website':True,
            'banner_title':banner_title,
            'banner_image':banner_image,
            'enable_forget_pwd':enable_forget_pwd,
            'enable_login':enable_login,
            'enable_signup':enable_signup,
            'website_name' : request.env['website'].search([])[0].name,
            'how_it_work_title':how_it_work_title,
            'how_it_work_text'  :how_it_work_text
        }
        if request.session.get('error'):
            values.update({'error':request.session.get('error')})
        if request.session.get('success'):
            values.update({'success':request.session.get('success')})
        request.session.pop('error', None)
        request.session.pop('success', None)
        response = http.request.render('affiliate_management.affiliate', values)
        aff_key = request.httprequest.args.get('aff_key')
        if aff_key:
            partner_id = request.env['res.partner'].sudo().search([('res_affiliate_key','=',aff_key),('is_affiliate','=',True)])
            if len(partner_id) == 1:
                expire = self.calc_cookie_expire_date()
                response.set_cookie(key='affkey_%s'%(aff_key), value='shop', expires=expire)
        return response


    @http.route('/affiliate/join', auth='public',type='json', website=True,methods=['POST'], sitemap=False)
    def join(self,email ,**kw):
        """
            Controller to create an affiliate joining request by the public user.
            They will get the response message according to the status of their affiliate request.
        """
        msg = False
        user=None
        aff = request.env['affiliate.request'].sudo().search([('name','=',email)])
        if aff:
            if (not aff.signup_valid) and (not aff.user_id):
                aff.regenerate_token()
                msg = _('Thank you for registering with us, we have sent you the Signup mail at {}.').format(email)

            else:
                website_name = aff.website_id.name 
                if aff.state == 'aproove':
                    msg = _("Your email is already registered with us on website %s.", website_name)
                elif aff.state == 'register':
                    msg = _("Your request is pending for approval with us on website %s, soon you will receive 'Approval' confirmation e-mail.", website_name)
                else:
                    if aff.user_id:
                        msg = _("Your request is pending for approval with us on website %s, soon you will receive 'Approval' confirmation e-mail.", website_name)
                    else:
                        msg = _("We have already sent you a joining e-mail from website  %s.", website_name)

        else:
            user = request.env['res.users'].sudo().search([('login','=',email)])
            msg = _("Thank you for registering with us, we have sent you the Signup mail at "+email)
            current_website = request.website
            vals = {
                'name':email,
                'state':'draft',
                'website_id': current_website.id
            }
            if user:
                vals.update({
                    "partner_id":user.partner_id.id,
                    "user_id" : user.id,
                    'state' : 'register'
                })
                msg = _("Your request is pending for approval with us, soon you will receive 'Approval' confirmation e-mail.")
            aff_request = request.env['affiliate.request'].sudo().create(vals)
        return msg

    @http.route('/affiliate/about',type='http', auth="user", website=True, sitemap=False)
    def affiliate_about(self, **kw):
        """
            Controller to visit the affiliate about page.
        """
        partner = request.env.user.partner_id
        base_url = request.website.domain or request.httprequest.host_url[:-1]
        currency_id = request.env.user.company_id.currency_id
        ConfigValues = request.env['res.config.settings'].sudo().website_constant(request.website)
        db = request.session.get('db')
        value={
            'url': "%s/shop?aff_key=%s&db=%s" %(base_url,partner.res_affiliate_key,db),
            'affiliate_key': partner.res_affiliate_key,
            'pending_amt':partner.pending_amt,
            'approved_amt':partner.approved_amt,
            'currency_id':currency_id,
            'how_it_works_title':ConfigValues.get('work_title'),
            'how_it_works_text':tools.html_sanitize(ConfigValues.get('work_text')),
            'page_name': 'affiliate_about',
        }
        return http.request.render('affiliate_management.about', value)

    @http.route('/affiliate/signup', auth='public',type='http', website=True, sitemap=False)
    def register(self, **kw):
        """
            Controller to visit the affiliate registration page.
        """
        token = request.httprequest.args.get('token')
        user = request.env['affiliate.request'].sudo().search([('signup_token','=',token)])
        term_condition = request.env['res.config.settings'].sudo().website_constant(request.website).get('term_condition')
        values = {}
        if user.signup_valid and user.state == 'draft':
            user_name = None
            if user.partner_id:
                user_name = user.partner_id.name
            else:
                user_name = user.name.split('@')[0]
            values .update({
                    'name': user_name,
                    'login': user.name,
                    'token': token,
                    'term_condition':tools.html_sanitize(term_condition),
                })
            if request.session.get('error'):
                values.update({'error':request.session.get('error')})
        else:
            pass
        request.session.pop('error', None)
        return http.request.render('affiliate_management.register',values)


    @http.route('/affiliate/register', auth='public',type='http', website=True, sitemap=False)
    def register_affiliate(self, **kw):
        """
            Controller to register the new user for the affiliate.
        """
        ensure_db()
        aff_request = request.env['affiliate.request'].sudo().search([('name','=',kw.get('login'))])
        if aff_request and kw.get('confirm_password') == kw.get('password') and aff_request.signup_token == kw.get('token'):
            template_user_id = literal_eval(request.env['ir.config_parameter'].sudo().get_param('base.template_portal_user_id', 'False'))
            template_user = request.env['res.users'].sudo().browse(template_user_id)
            auto_approve_request = request.env['res.config.settings'].sudo().website_constant().get('auto_approve_request')
            if not template_user.exists():
                raise SignupError('Invalid template user.')
            data = kw
            values = { key: data.get(key) for key in ('login', 'name') }
            values['email'] = data.get('email') or values.get('login')
            values['lang'] = request.lang.code
            values['active'] = True
            no_invitation_mail = True
            values['password'] = data.get('password',"")
            try:
                with request.env.cr.savepoint():
                    user = template_user.with_context(no_reset_password = no_invitation_mail).copy(values)
                    _logger.info('------user.partner--%r-----',user.partner_id)
                    # update phoen no. and comment in res.partner
                    user.partner_id.comment = kw.get('comment')
                    user.partner_id.phone = kw.get('phone')
                    # update affiliate.request with partner and user id and state
                    aff_request.partner_id = user.partner_id.id
                    aff_request.user_id = user.id
                    aff_request.state = 'register'
                request.env.cr.commit()
                # check the config for auto approve the request
                if auto_approve_request:
                    aff_request.action_aproove()
                db = request.session.db
                credential = {'login': data.get('email') or values.get('login'), 'password': data.get('password',""), 'type': 'password'}
                uid = request.session.authenticate(db, credential)
                return request.redirect(_get_login_redirect_url(uid, redirect='/affiliate'))

            except Exception as e:
                _logger.error("Error While creating the affiliate user: %r"%e)
            return request.redirect('/')
        else:
            if kw.get('password')!= kw.get('confirm_password'):
                request.session['error']= _("Passwords Doesn't match.")
                return request.redirect('/affiliate/signup?token='+kw.get('token'), 303)
            else:
                request.session['error']= _("something went wrong..")
                return request.redirect('/affiliate/', 303)



    @http.route('/affiliate/report', type='http', auth="user", website=True, sitemap=False)
    def report(self, **kw):
        """
            Controller to visit the affiliate report page.
        """
        partner = request.env.user.partner_id
        enable_ppc = request.env['res.config.settings'].sudo().website_constant().get('enable_ppc')
        currency_id = request.env.user.company_id.currency_id
        visits = request.env['affiliate.visit'].sudo()
        ppc_visit = visits.search([('website_id', '=', request.website.id),('affiliate_method','=','ppc'),('affiliate_partner_id','=',partner.id),('state','in',['invoice', 'confirm', 'paid'])])
        pps_visit = visits.search([('website_id', '=', request.website.id),('affiliate_method','=','pps'),('affiliate_partner_id','=',partner.id),('state','in',['invoice', 'confirm', 'paid'])])
        values = {
        'pending_amt':partner.pending_amt,
        'approved_amt':partner.approved_amt,
        'ppc_count':len(ppc_visit),
        'pps_count':len(pps_visit),
        'enable_ppc':enable_ppc,
        "currency_id":currency_id,
        "page_name": 'reports'
        }
        return http.request.render('affiliate_management.report', values)
    
    @http.route(['/my/commissions','/my/commissions/page/<int:page>'], type='http', auth="user", website=True, sitemap=False)
    def commissions(self, page=1, date_begin=None, date_end=None, **kw):
        """
            Controller to visit the affiliate commissions page.
        """
        values={}
        partner = request.env.user.partner_id
        visits = request.env['affiliate.visit'].sudo()
        domain = [('website_id', '=', request.website.id), ('affiliate_partner_id','=',partner.id), ('state','in',['invoice', 'confirm', 'paid'])]
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]
        commissions_count = visits.search_count(domain)
        pager = request.website.pager(
            url='/my/commissions',
            url_args={'date_begin': date_begin, 'date_end': date_end},
            total=commissions_count,
            page=page,
            step=10
        )
        all_visit = visits.search(domain, limit=10, offset=pager['offset'], order="id desc")
        values.update({
            'pager': pager,
            'commissions': all_visit,
            'default_url': '/my/commissions',
            'page_name': 'earned_commissions'
        })

        return http.request.render('affiliate_management.portal_my_affiliate_all_reports', values)

    @http.route(['/my/traffic','/my/traffic/page/<int:page>'], type='http', auth="user", website=True, sitemap=False)
    def traffic(self, page=1, date_begin=None, date_end=None, **kw):
        """
            Controller to visit the affiliate traffic report page.
        """
        values={}
        partner = request.env.user.partner_id
        visits = request.env['affiliate.visit'].sudo()
        domain = [('website_id', '=', request.website.id), ('affiliate_partner_id','=',partner.id),('affiliate_method','=','ppc'),('state','in',['invoice', 'confirm', 'paid'])]
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]
        traffic_count = visits.search_count(domain)
        pager = request.website.pager(
            url='/my/traffic',
            url_args={'date_begin': date_begin, 'date_end': date_end},
            total=traffic_count,
            page=page,
            step=10
        )
        ppc_visit = visits.search(domain, limit=10, offset=pager['offset'])
        values.update({
            'pager': pager,
            'traffic': ppc_visit,
            'default_url': '/my/traffic',
            'page_name': 'ppc_reports'
        })

        return http.request.render('affiliate_management.affiliate_traffic', values)


    @http.route(['/my/traffic/<int:traffic>'], type='http', auth="user", website=True, sitemap=False)
    def aff_traffic_form(self, traffic=None, **kw):
        """
            Controller to visit the affiliate traffic report details page.
        """
        traffic_visit = request.env['affiliate.visit'].sudo().browse([traffic])
        return request.render("affiliate_management.traffic_form", {
            'traffic_detail': traffic_visit,
            'product_detail':request.env['product.product'].browse([traffic_visit.type_id]),
        })



    @http.route(['/my/order','/my/order/page/<int:page>'], type='http', auth="user", website=True, sitemap=False)
    def aff_order(self, page=1, date_begin=None, date_end=None, **kw):
        """
            Controller to visit the affiliate order report page.
        """
        values={}
        partner = request.env.user.partner_id
        visits = request.env['affiliate.visit'].sudo()
        domain = [('website_id', '=', request.website.id), ('affiliate_partner_id','=',partner.id),('affiliate_method','=','pps'),('state','in',['invoice', 'confirm', 'paid'])]
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]
        traffic_count = visits.search_count(domain)
        pager = request.website.pager(
            url='/my/order',
            url_args={'date_begin': date_begin, 'date_end': date_end},
            total=traffic_count,
            page=page,
            step=10
        )
        ppc_visit = visits.sudo().search(domain, limit=10, offset=pager['offset'])
        values.update({
            'pager': pager,
            'traffic': ppc_visit,
            'default_url': '/my/order',
            'page_name': 'pps_reports'
        })
        return http.request.render('affiliate_management.affiliate_order', values)


    @http.route(['/my/order/<int:order>'], type='http', auth="user", website=True, sitemap=False)
    def aff_order_form(self, order=None, **kw):
        """
            Controller to visit the affiliate order report details page.
        """
        order_visit = request.env['affiliate.visit'].sudo().browse([order])
        return request.render("affiliate_management.order_form", {
            'order_visit_detail': order_visit,
            'product_detail' :order_visit.sales_order_line_id.sudo()
        })


    @http.route(['/affiliate/payment','/affiliate/payment/page/<int:page>'], type='http', auth="user", website=True, sitemap=False)
    def payment(self, page=1, date_begin=None, date_end=None, **kw):
        """
            Controller to visit the affiliate payment page.
        """
        values={}
        partner = request.env.user.partner_id
        invoices = request.env['account.move']
        domain = [('partner_id','=',partner.id),('payment_state','=','paid'),('ref','=',None)]
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]
        invoice_count = invoices.search_count(domain)

        pager = request.website.pager(
            url='/affiliate/payment',
            url_args={'date_begin': date_begin, 'date_end': date_end},
            total=invoice_count,
            page=page,
            step=10
        )
        invoice_list = invoices.search(domain, limit=10, offset=pager['offset'])

        values.update({
            'pager': pager,
            'invoices': invoice_list,
            'default_url': '/affiliate/payment',
            'page_name': 'affiliate_payments',
        })
        return http.request.render('affiliate_management.payment_tree',values )


    @http.route(['/my/invoice/<int:invoice>'], type='http', auth="user", website=True, sitemap=False)
    def aff_invoice_form(self, invoice=None, **kw):
        """
            Controller to visit the affiliate payment details page.
        """
        inv = request.env['account.move'].sudo().browse([invoice])
        return request.render("affiliate_management.payment_form", {
            'invoice': inv,
        })

    @http.route('/affiliate/tool', auth='user',type='http', website=True, sitemap=False)
    def tool(self, **kw):
        """
            Controller to visit the affiliate tool page.
        """
        return http.request.render('affiliate_management.tool',{'page_name': 'affiliate_tools'})


    @http.route('/tool/create_link', auth='user',type='http', website=True, sitemap=False)
    def create_link(self, **kw):
        """
            Controller to generate affiliate link using current url.
        """
        partner = request.env.user.partner_id
        link = kw.get("link") if kw.get("link").find('#') != -1 else str(kw.get("link"))+'#' 
        index_li = link.find('#')
        attr_li = link.find('?')
        db = request.session.get('db')
        db = "%sdb=%s" %('?' if attr_li==-1 else '&', db)
        link = link[:index_li]+db+link[index_li:]
        result = self.check_link_validation(link)
        if kw.get('link') and partner.res_affiliate_key and result:
            index_li = link.find('#')
            request.session['generate_link'] = link[:index_li]+'&aff_key='+partner.res_affiliate_key+link[index_li:]
        return request.redirect('/tool/link_generator/', 303)

    @http.route("/tool/link_generator", auth='user',type='http', website=True, sitemap=False)
    def link_generator(self, **kw):
        """
            Controller to visit the affiliate link generator page.
        """
        partner = request.env.user.partner_id
        values={
            'page_name': 'affiliate_link_generator',
        }
        if request.session.get('generate_link'):
            values.update({
                'generate_link':request.session.get('generate_link'),
                'error':request.session.get('error')
                })
        if request.session.get('error'):
            values.update({
                'error':request.session.get('error')
                })
        request.session.pop('generate_link', None)
        request.session.pop('error', None)
        return http.request.render('affiliate_management.link_generator',values)

    def check_link_validation(self,link):
        """
            Method to validate the link entered by the affiliate to genertae affiliate link.
        """
        base_url = request.website.domain or request.httprequest.host_url[:-1]
        try:
            r = requests.get(link,verify=False)

            if r.status_code == 200:
                langs = [l.code for l in request.website.language_ids]

                link_arr = link.split("/")
                # if a language is already in the path, remove it
                if link_arr[1] in langs:
                    link_arr.pop(1)
                link_base_url = link_arr[0]+"//"+link_arr[2]

                if base_url == link_base_url :
                    if 'shop' in link_arr or 'product' in link_arr:
                        return True
                    else:
                        request.session['error'] = "Url doesn't have shop/product"
                        return False
                else:
                    request.session['error'] = "Base Url doesn't match"
                    return False
            else:
                request.session['error'] = "Please enter a Valid Url. Bad response from "+link
                return False
        except Exception as e:
            request.session['error'] = "Please enter a Valid Url. + %r"%e
            return False




    @http.route("/tool/product_link", auth='user',type='http', website=True, sitemap=False)
    def product_link(self, **kw):
        """
            Controller to visit the affiliate product link page.
        """
        values={}
        category = request.env['product.public.category'].sudo().search([])
        values.update({
            'category': category,
            'page_name': 'affiliate_product_link',
            })
        return http.request.render('affiliate_management.product_link',values)


    @http.route("/search/product", auth='user',type='http', website=True, sitemap=False)
    def search_product(self, **kw):
        """
            Controller to search the product on criteria category and published product 
            from the affiliate product link page.
        """
        domain = request.website.sale_product_domain()
        if kw.get('name'):

            domain += [
                ('website_published','=',True),'|', '|', '|', ('name', 'ilike', kw.get('name')), ('description', 'ilike', kw.get('name')),
                ('description_sale', 'ilike', kw.get('name')), ('product_variant_ids.default_code', 'ilike', kw.get('name'))]

        if kw.get('categories'):
            category_id = request.env['product.public.category'].sudo().search([('name','=',kw.get('categories'))],limit=1)
            if  category_id:
                domain += [('public_categ_ids', 'child_of', int(category_id.id))]

        partner = request.env.user.partner_id
        values={}
        category = request.env['product.public.category'].sudo().search([])
        values.update({
            'category': category,
            })
        product_template = request.env['product.template'].sudo()
        products = product_template.search(domain)
        db = request.session.get('db')
        if products:
            values.update({
                'bins': TableCompute().process(products, 10),
                'search_products':products,
                'rows':4,
                'partner_key': partner.res_affiliate_key,
                'base_url': request.website.domain or request.httprequest.host_url[:-1],
                'db':db,
                'page_name': 'affiliate_product_link',
                })
        return http.request.render('affiliate_management.product_link',values)


    @http.route('/tool/generate_banner', auth='user',type='http', website=True, sitemap=False)
    def tool_banner(self, **kw):
        """
            Controller to visit the generate affiliate banner page.
        """
        partner = request.env.user.partner_id
        banner_image_ids = request.env['affiliate.image'].sudo().search([('image_active','=',True)])
        product = request.env['product.template'].sudo().search([('id','=',kw.get('product_id'))])
        db = request.session.get('db')
        values={
            'banner_button':banner_image_ids,
            'product':product,
            'db':db,
            'page_name': 'affiliate_product_link',
        }
        return http.request.render('affiliate_management.generate_banner',values)


    @http.route("/tool/generate_button_link", auth='user',type='http', website=True, sitemap=False)
    def generate_button_link(self, **kw):
        """
            Controller to generate the product affiliate banner and display it on the banner page.
        """
        partner = request.env.user.partner_id
        base_url = request.website.domain or request.httprequest.host_url[:-1]
        db = request.session.get('db')
        values ={
            'partner_key': partner.res_affiliate_key,
            'product_id':kw.get('product_id'),
            'base_url' : base_url,
            'db':db,
            'page_name': 'affiliate_product_link',
        }
        selected_image= kw.get('choose_banner').split("_")
        if selected_image[0] == 'button':
            _logger.debug("-----selected button image id ---%r---",selected_image[1])
            button = request.env['affiliate.image'].sudo().browse([int(selected_image[1])])
            values.update({
                "button":button
                })
        else:
            if selected_image[0] == 'product':
                values.update({
                "is_product":True
                })
                _logger.debug("-----selected product image id ---%r---",selected_image[1])
        return http.request.render('affiliate_management.generate_button_link',values)



    @http.route("/affiliate/request", type='json', auth="public", methods=['POST'], website=True, sitemap=False)
    def portal_user(self, user_id,**kw):
        """
            Controller for requesting for the affiliate by the portal user.
        """
        User = request.env['res.users'].sudo().browse([request.uid])
        AffRqstObj = request.env['affiliate.request'].sudo()
        current_website = request.website
        vals ={
        'name':User.partner_id.email,
        'partner_id': User.partner_id.id,
        'user_id': request.uid,
        'website_id': current_website.id,
        'state':'register',
        }
        aff_request = AffRqstObj.create(vals)
        auto_approve_request = request.env['res.config.settings'].sudo().website_constant().get('auto_approve_request')
        if aff_request.state=='register' and auto_approve_request:
            aff_request.action_aproove()
        return aff_request and True or False
    

    @http.route("/my/affiliate", type='http', auth="user", methods=['GET'], website=True, sitemap=False)
    def my_affiliate_home(self, **kw):
        """
            Controller to visit the affiliate home page.
        """
        partner = request.env.user.partner_id
        aff_visits = request.env['affiliate.visit'].sudo().search([('affiliate_partner_id', '=', partner.id), ('website_id', '=', request.website.id)])
        clicks = len(aff_visits.filtered(lambda v: v.affiliate_method=='ppc' and v.state in ['confirm', 'invoice', 'paid']))
        orders = len(aff_visits.filtered(lambda v: v.affiliate_method=='pps' and v.state in ['confirm', 'invoice', 'paid']))
        currency_id = request.env.user.company_id.currency_id
        commission_earned = sum(aff_visits.filtered(lambda v: v.affiliate_method in ['ppc', 'pps'] and v.state in ['confirm', 'invoice', 'paid']).mapped('commission_amt'))
        commission_cleared = sum(aff_visits.filtered(lambda v: v.affiliate_method in ['ppc', 'pps'] and v.state in 'paid').mapped('commission_amt'))
        invoices_count = request.env['account.move'].sudo().search_count([('partner_id','=',partner.id),('payment_state','=','paid'),('ref','=',None)])
        partner_aff_program = request.env['affiliate.program'].sudo().search([('website_id', '=', request.website.id)], limit=1)
        base_url = request.website.domain or request.httprequest.host_url[:-1]
        db = request.session.get('db')
        values = {
            'url': "%s/affiliate?aff_key=%s&db=%s" %(base_url,partner.res_affiliate_key,db),
            "affiliate_key": partner.res_affiliate_key,
            "clicks": clicks,
            "orders": orders,
            'currency_id':currency_id,
            "commission_earned": round(commission_earned, 2),
            "commission_cleared": round(commission_cleared, 2),
            "invoices_count": invoices_count,
            "partner_aff_program": partner_aff_program,
            "page_name": 'affiliate_home'
        }
        return http.request.render('affiliate_management.portal_my_affiliate_home', values)
    
    @http.route("/affiliate/summary", type='http', auth="user", methods=['GET'], website=True, sitemap=False)
    def my_affiliate_summary(self, **kw):
        """
            Controller to visit the affiliate summary page.
        """
        partner = request.env.user.partner_id
        aff_visits = request.env['affiliate.visit'].sudo().search([('affiliate_partner_id', '=', partner.id), ('website_id', '=', request.website.id)])
        ppc_visits = aff_visits.filtered(lambda v: v.affiliate_method=='ppc' and v.state in ['confirm', 'invoice', 'paid'])
        confirmed_orders = aff_visits.filtered(lambda v: v.affiliate_method=='pps' and v.state in ['paid'])
        pending_orders = aff_visits.filtered(lambda v: v.affiliate_method=='pps' and v.state in ['confirm', 'invoice'])
        clicks = len(ppc_visits)   
        unique_clicks = len(set(ppc_visits.mapped('ip_address')))
        base_url = request.website.domain or request.httprequest.host_url[:-1]
        currency_id = request.env.user.company_id.currency_id
        db = request.session.get('db')
        partner_aff_program = request.env['affiliate.program'].sudo().search([('website_id', '=', request.website.id)], limit=1)

        values = {
            'url': "%s/shop?aff_key=%s&db=%s" %(base_url,partner.res_affiliate_key,db),
            'affiliate_key': partner.res_affiliate_key,
            'pending_amt':partner.pending_amt,
            'approved_amt':partner.approved_amt,
            'currency_id':currency_id,
            'clicks': clicks,
            'unique_clicks':unique_clicks,
            'confirmed_orders': len(confirmed_orders),
            'pending_orders': len(pending_orders), 
            "page_name": 'summary',
            "partner_aff_program": partner_aff_program,
        }
        return http.request.render('affiliate_management.affiliate_summary', values)
    


    @http.route("/affiliate/statistics", type='http', auth="user", methods=['GET'], website=True, sitemap=False)
    def my_affiliate_statistics(self, **kw):
        """
            Controller to visit the affiliate statistics page.
        """
        values= {
            "page_name": "affiliate_statistics"
        }
        return http.request.render('affiliate_management.portal_my_affiliate_statistics', values)
    

    @http.route("/affiliate/program/commission", type='http', auth="user", methods=['GET'], website=True, sitemap=False)
    def my_affiliate_program_commission(self, **kw):
        """
            Controller to visit the affiliate program advance commission page.
        """
        partner_aff_program = request.env['affiliate.program'].sudo().search([('website_id', '=', request.website.id)], limit=1)
        currency_id = request.env.user.company_id.currency_id
        values= {
            "partner_aff_program": partner_aff_program,
            "adv_commission": partner_aff_program.advance_commision_id,
            'currency_id':currency_id,
            "page_name": "affiliate_program_commission"
        }
        return http.request.render('affiliate_management.portal_my_affiliate_program_commission', values)
    
    
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


