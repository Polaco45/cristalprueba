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

class AffiliateImage(models.Model):
    _name = "affiliate.image"
    _description = "Affiliate Image Model"
    _inherit = ['mail.thread']


    name = fields.Char(string = "Name",required=True, help="Name of the affiliate image")
    title = fields.Char(string = "Title",required=True, help="Title of the affiliate image")
    banner_height = fields.Integer(string = "Height", help="Height of the affiliate image")
    bannner_width =  fields.Integer(string = "Width", help="Width of the affiliate image")
    image = fields.Binary(string="Image",required=True, help="Select the image for the affiliate image")
    user_id = fields.Many2one('res.users', string='Current User', index=True, tracking=True, default=lambda self: self.env.user)
    image_active = fields.Boolean(string="Active",default=True)


    def toggle_active_button(self):
        """
            Method used to toggle the active status of the affiliate image
        """
        if self.image_active:
            self.image_active = False
        else:
            self.image_active = True


    @api.model_create_multi
    def create(self,vals_list):
        for vals in vals_list:
            if vals.get('image') == False:
                raise UserError(_("Image field is mandatory"))
        return super(AffiliateImage,self).create(vals_list)
