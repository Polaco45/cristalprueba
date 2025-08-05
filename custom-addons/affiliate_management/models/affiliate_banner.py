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

class AffiliateBanner(models.Model):
    _name = "affiliate.banner"
    _description = "Affiliate Banner Model"

    banner_title = fields.Text(string="Banner Text", help="Text for the affiliate banner.")
    banner_image = fields.Binary(string="Banner Image", help="Background Image for the affiliate banner.")


    @api.model_create_multi
    def create(self,vals_list):
        for vals in vals_list:
            if vals.get('banner_image') == False:
                raise UserError(_("Image field is mandatory"))
        return super(AffiliateBanner,self).create(vals_list)
