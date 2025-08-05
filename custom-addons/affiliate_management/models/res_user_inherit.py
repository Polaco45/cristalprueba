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

class ResUserInherit(models.Model):

	_inherit = 'res.users'
	_inherits = {'res.partner': 'partner_id'}

	res_affiliate_key = fields.Char(related='partner_id.res_affiliate_key',string='Partner Affiliate Key', inherited=True)

