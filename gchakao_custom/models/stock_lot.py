# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression

class StockLot(models.Model):
    _inherit = 'stock.lot'

    tracking_number = fields.Char(
        string='Número de Seguimiento',
        index=True,
    )

    @api.depends('name','tracking_number')
    def _compute_display_name(self):
        for rec in self:
            if rec.tracking_number:
                rec.display_name = f'{rec.name}-{rec.tracking_number}'
            else:
                rec.display_name = rec.name

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None, order=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('name', operator, name), ('tracking_number', operator, name)]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid, order=order)

    @api.constrains('tracking_number')
    def _check_tracking_number(self):
        for rec in self.filtered(lambda p: p.tracking_number):
            domain = [('id', '!=', rec.id), ('tracking_number', '=', rec.tracking_number)]
            if self.search(domain):
                raise UserError(_('En numero de seguimiento %s ya se encuentra asignado al producto %s')%(rec.tracking_number, rec.product_id.name))