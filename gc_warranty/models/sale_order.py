# coding: utf-8
from odoo import models, fields, api, _
from datetime import datetime
from odoo.exceptions import UserError, ValidationError

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    is_warranty = fields.Boolean(
        string='Es una Garantía',
        copy=False,
        default=False,
        tracking=True,
    )
    
    warranty_id = fields.Many2one(
        'warranty.request',
        string='warranty',
        copy=False,
    )

    @api.onchange('warranty_id')
    def _onchange_warranty_id(self):
        if self.warranty_id:
            self.partner_id = self.warranty_id.partner_id
            self.user_id = self.warranty_id.user_id
            self.is_warranty = True

    @api.onchange('is_warranty')
    def _onchange_is_warranty(self):
        if not self.is_warranty:
            self.partner_id = False
            self.user_id = False
            self.is_warranty = False
            self.warranty_id = False


    
    