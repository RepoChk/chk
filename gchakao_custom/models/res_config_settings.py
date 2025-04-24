# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, SUPERUSER_ID


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hr_payment_order_notification_user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        config_parameter='gchakao_custom.hr_payment_order_notification_user_id',
    )

    account_payment_notification_user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        config_parameter='gchakao_custom.account_payment_notification_user_id',
    )
