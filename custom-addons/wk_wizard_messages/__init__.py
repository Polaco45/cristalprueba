# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from . import wizard


def pre_init_check(cr):

    # Odoo Module
	from odoo.service import common
	from odoo.exceptions import ValidationError
	from odoo import _

	version_info = common.exp_version()
	server_serie = version_info.get('server_serie')
	if server_serie != '18.0':
		raise ValidationError(_('Module support Odoo series 18.0 found {}.'.format(server_serie)))
