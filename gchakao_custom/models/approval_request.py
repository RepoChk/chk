# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    approving_amount= fields.Float(string='Monto Limite de Aprobación de OC')
    next_approver_ids = fields.Many2many('res.users', string='Siguiente Aprobador')
    previous_approver_ids = fields.Many2one('res.users', string='Anterior Aprobador')
    is_next_approver = fields.Boolean(string='Requiere mas Aprobaciones')
    purchase_id = fields.Many2one('purchase.order', string='Pedido de Compra')
    is_purchase = fields.Selection(related="category_id.is_purchase")
    order_id = fields.Many2one('sale.order', string='Pedido de Venta')
    amount_purchase = fields.Monetary(string='Monto de la Compra', currency_field='currency_id_dif', store=True)
    amount = fields.Monetary(string='Monto', currency_field='currency_id_dif', compute='_compute_field', store=True)
    is_order = fields.Selection(related='category_id.is_order')

    payment_order_id = fields.Many2one('hr.payment.order', string='Orden de Pago')
    is_order_payment = fields.Selection(related="category_id.is_order_payment")

    currency_id_dif = fields.Many2one(
        'res.currency',
        string='Moneda referencia',
        default=lambda self: self.env.company.currency_id_dif,
        readonly=True, 
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda de la compañía',
        default=lambda self: self.env.company.currency_id,
        readonly=True, 
    )

    credit_limit = fields.Monetary(
        default=0, 
        string='Límite de Crédito',
        tracking=True, 
        currency_field='currency_id_dif', 
        compute='_compute_field', 
        store=True
    )

    available_credit = fields.Monetary(
        string='Crédito Disponible', 
        default=0, 
        compute='_compute_field', 
        currency_field='currency_id_dif', 
        store=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Contacto',
        compute='_compute_field'
    )

    group_name = fields.Char(string='Nombre del Grupo', compute='_compute_group_info', store=True)
    group_total_credit_limit = fields.Monetary(
        string='Crédito Total Límite del Grupo', 
        compute='_compute_group_info',
        currency_field='currency_id_dif',
        store=True
    )
    group_credit_difference = fields.Monetary(
        string='Crédito Utilizado del Grupo', 
        compute='_compute_group_info',
        currency_field='currency_id_dif',
        store=True
    )
    group_available_credit = fields.Monetary(
        string='Crédito Disponible del Grupo', 
        compute='_compute_group_info',
        currency_field='currency_id_dif',
        store=True
    )

    @api.depends('order_id')
    def _compute_field(self):
        for record in self:
            record.amount = record.order_id.amount_total if record.order_id else 0.0
            record.partner_id = record.order_id.partner_id if record.order_id.partner_id else False
            record.credit_limit = record.order_id.partner_id.credit_limit if record.order_id and record.order_id.partner_id else 0.0
            record.available_credit = record.order_id.partner_id.available_credit if record.order_id and record.order_id.partner_id else 0.0

    @api.depends('partner_id.customer_group_id')
    def _compute_group_info(self):
        for record in self:
            group = record.partner_id.customer_group_id
            if group:
                record.group_name = group.name
                record.group_total_credit_limit = group.total_credit_limit
                record.group_credit_difference = group.credit_difference
                record.group_available_credit = group.available_credit_group
            else:
                # Reset to default values if no group is assigned
                record.group_name = False
                record.group_total_credit_limit = 0.0
                record.group_credit_difference = 0.0
                record.group_available_credit = 0.0

    def action_next_approve(self):
        for next_aprover in self:
            if not next_aprover.next_approver_ids:
                raise ValidationError(
                    "No tiene Asignado el Lider Aprobador en el registro de usuario."
                     "Vaya a Ajuste / Usuario y compañia / Usuario.")
                
            next_aprover.write({'request_status': 'approved','date_confirmed': fields.Datetime.now()})
            
            for approval in next_aprover.next_approver_ids:
                if next_aprover.purchase_id: 
                    if next_aprover.amount_purchase >= approval.approving_amount:
                        state=True
                        break
                    if approval.approving_amount >= next_aprover.amount_purchase:
                        state=False
                        break

            approval_request = self.env['approval.request'].create({
                'name': next_aprover.name,
                'category_id': next_aprover.category_id.id,
                'date': datetime.now(),
                'request_owner_id': next_aprover.request_owner_id.id,
                'reference': next_aprover.reference,
                'partner_id': next_aprover.partner_id.id,
                'approving_amount': approval.approving_amount,
                'next_approver_ids': next_aprover.next_approver_ids.approving_leader_oc_ids.ids,
                'previous_approver_ids': next_aprover.env.user.id,
                'is_next_approver': state,
                'amount_purchase': next_aprover.amount_purchase,
                'purchase_id': next_aprover.purchase_id.id,
                'request_status': 'pending'
            })
                    
            for item in next_aprover.next_approver_ids:
                self.env['approval.approver'].create({
                    'user_id': item.id,
                    'request_id': approval_request.id,
                    'status': 'pending'
                })
            approval_request.action_confirm()
       
    def action_approve(self, approver=None):
        if self.is_next_approver:
            raise ValidationError('Disculpe, debe solicitar la segunda aprobación')
        res = super(ApprovalRequest, self).action_approve(approver=None)
        
        if self.is_order_payment and self.payment_order_id:
            if self.payment_order_id.state not in ['approved', 'rejected']:
                self.payment_order_id.action_approve()
        
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        
        self.write({'date_confirmed': fields.Datetime.now()})
        return res

    def action_refuse(self, approver=None):
        res = super(ApprovalRequest, self).action_refuse(approver=None)
        if self.is_order_payment:
            self.payment_order_id.action_rejected()
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        return res