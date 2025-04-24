# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, SUPERUSER_ID


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    warranty_order_user_id = fields.Many2one(
        'res.users',
        string='Usuario responsable del pedido',
        config_parameter='gc_warranty.warranty_order_user_id',
    )

    warranty_close_user_id = fields.Many2one(
        'res.users',
        string='Usuario responsable de cerrar la garantía',
        config_parameter='gc_warranty.warranty_close_user_id',
    )
