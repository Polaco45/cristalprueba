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


class AffiliateCommision(models.Model):
    _name = "advance.commision"
    _description = "Affiliate Commision Model"

    name = fields.Char(string="Name", required=True, help="Name of the advance affiliate commission")
    pricelist_item_ids = fields.One2many("affiliate.product.pricelist.item",'advance_commision_id',string="Item", help="List of Affiliate Product Pricelist Items")
    active_adv_comsn = fields.Boolean(default=True,string="Active")


    def toggle_active_button(self):
        if self.active_adv_comsn:
            self.active_adv_comsn = False
        else:
            self.active_adv_comsn = True

    def calc_commision_adv(self, adv_comsn_id, product_templ_id , product_price):
        """
            Method to calculate the advance commission based on either the product category, 
            or specific product, or specific product variant, or globally.
            
            [Arguments]: advance commission, product template, and product price. 
        """
        _logger.debug("-----in advance commision model-- method-- calc_commision_adv-----")
        product_tmpl_category_ids = self.env['product.template'].browse([product_templ_id]).public_categ_ids
        _logger.debug("**********-----product_tmpl_category_ids--%r********",product_tmpl_category_ids)

        pricelist_ids = self.env['affiliate.product.pricelist.item'].search([('advance_commision_id','=',adv_comsn_id)])
        for pricelist_id in pricelist_ids:
            _logger.info("***====pricelist_id.name=%r======",pricelist_id.name)

            commision_value = False
            commision_value_type = False
            adv_commision_amount = False

            """  on global product """
            if pricelist_id.applied_on == "3_global":
                if pricelist_id.compute_price == "fixed":
                    commision_value = pricelist_id.fixed_price
                    commision_value_type = 'fixed'
                    adv_commision_amount = pricelist_id.fixed_price
                else:
                    if pricelist_id.compute_price == "percentage":
                        commision_value = product_price * (pricelist_id.percent_price /100)
                        commision_value_type = 'percentage'
                        adv_commision_amount = pricelist_id.percent_price

            else:
                """ on  product category """
                if pricelist_id.applied_on == "2_product_category":
                    if pricelist_id.categ_id in product_tmpl_category_ids:
                        if pricelist_id.compute_price == "fixed":
                            commision_value = pricelist_id.fixed_price
                            commision_value_type = 'fixed'
                            adv_commision_amount = pricelist_id.fixed_price

                        else:
                            if pricelist_id.compute_price == "percentage":
                                commision_value = product_price * (pricelist_id.percent_price /100)
                                commision_value_type = 'percentage'
                                adv_commision_amount = pricelist_id.percent_price


                else:
                    """ on specific product """ 
                    if pricelist_id.applied_on == "1_product":
                        if product_templ_id == pricelist_id.product_tmpl_id.id:
                            if pricelist_id.compute_price == "fixed":
                                commision_value = pricelist_id.fixed_price
                                commision_value_type = 'fixed'
                                adv_commision_amount = pricelist_id.fixed_price

                            else:
                                if pricelist_id.compute_price == "percentage":
                                    commision_value = product_price * (pricelist_id.percent_price /100)
                                    commision_value_type = 'percentage'
                                    adv_commision_amount = pricelist_id.percent_price


            if commision_value and commision_value_type:
                break
            # this break is used for if advance commission found in pricelist ids
            #  then it will break so that further pricelist ids is not executed in for loop
            # this is for calculation advance commission base on global, perticular product or category
        return adv_commision_amount,commision_value , commision_value_type

