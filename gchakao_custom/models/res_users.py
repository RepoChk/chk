# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import UserError, RedirectWarning
from datetime import timedelta, datetime, date

class ResUsers(models.Model):
    _inherit = 'res.users'

    warehouse_ids = fields.Many2many(
        'stock.warehouse',
        string='Almacenes',
    )

    payment_term_ids = fields.Many2many(
        'account.payment.term',
        string='Términos de pago',
        help='Seleccione los términos de pago permitidos para este usuario', 
    )

    approving_amount= fields.Float(string='Monto Limite de Aprobación OC')
    
    approving_leader_oc_ids= fields.Many2many(
        'res.users', 
        'approver_oc_id', 
        'users_id', 
        string='Lider Aprobador OC'
    )

    remove_approval = fields.Boolean(
        string='Permitir deshabilitar aprobaciones',
        help='Este permiso permite deshabilitar las aprobaciones en los pedidos de compra y ventas'
    )

    signature_seal = fields.Binary(
        string="Digital Signature", 
        company_dependent=True,
        copy=False, groups="base.group_system"
    )

    @api.onchange('warehouse_ids')
    def _onchange_warehouse_ids(self):
        if self.warehouse_ids:
            if not self.property_warehouse_id:
                self.property_warehouse_id = self.warehouse_ids[0].id
            else:
                if self.property_warehouse_id not in self.warehouse_ids:
                    self.property_warehouse_id = self.warehouse_ids[0].id

    @api.onchange('property_warehouse_id')
    def _onchange_property_warehouse_id(self):
        if self.property_warehouse_id:
            if self.share:
                if self.property_warehouse_id not in self.warehouse_ids:
                    self.property_warehouse_id = self.warehouse_ids[0].id
