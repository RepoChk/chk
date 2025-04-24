# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_warranty = fields.Boolean(
        string='Es garantia',
        default=False,
    )

    warranty_request_count = fields.Integer(
        string='# Mantenimientos',
        compute='_compute_maintenance_count'
    )

    warranty_ids = fields.One2many(
        'warranty.request',
        'product_id',
        string='Registro de garantias',
        domain=[('state','=','done'), ]
    )

    warranty_period = fields.Integer(
        string='Periodo de garantía',
    )

    def _compute_maintenance_count(self):
        for template in self:
            template.warranty_request_count = len(template.warranty_ids)

    def action_maintenance_view(self):
        action = {
            'name': _('Reg. garantias'),
            'type': 'ir.actions.act_window',
            'res_model': 'warranty.request',
            'target': 'current',
        }
        action['view_mode'] = 'tree'
        action['domain'] = [('id', 'in', self.warranty_ids.ids)]
        return action