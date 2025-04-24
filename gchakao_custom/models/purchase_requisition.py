# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PurchaseRequisition(models.Model):
    _inherit = "purchase.requisition"

    master_vendor_id = fields.Many2one(
        'res.partner', string='Fabrica'
    )

    sub_partner_ids = fields.Many2many(
        'res.partner',
        compute='_compute_sub_partner_ids',
    )

    @api.depends('master_vendor_id')
    def _compute_sub_partner_ids(self):
        for item in self:
            item.sub_partner_ids = item.master_vendor_id.sub_provider_ids.ids 
        
    def _prepare_purchase_order(self):
        purchase_vals = super(PurchaseRequisition, self)._prepare_purchase_order()
        purchase_vals.update({
            'sub_provider_id' : self.master_vendor_id,
        })
        return purchase_vals