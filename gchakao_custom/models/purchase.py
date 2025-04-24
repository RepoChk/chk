# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import datetime
from odoo.exceptions import UserError, ValidationError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"
    
    approvals_ids = fields.One2many(
        'approval.request', 
        'purchase_id', 
        string='Aprobaciones Enviadas'
    )

    approver_ids = fields.Many2many(
        'res.users', 
        string='Aprobadores', 
        readonly=True, 
        default=lambda x: x.env['res.users'].search([('id', '=', x.env.uid)]).approving_leader_oc_ids.ids,
        store=True
    )

    remove_approval = fields.Boolean(compute='_compute_remove_approval', store=True)

    @api.depends('user_id')
    def _compute_remove_approval(self):
        self.remove_approval = self.env.user.remove_approval
    
    is_approval = fields.Boolean(
        string="Tiene Aprobación", default=True,
    )
    is_approval_progress= fields.Boolean(
        string='Aprobaciones en Curso', compute='_Compute_approval_progress', readonly=True
    )

    sub_partner_ids = fields.Many2many(
        'res.partner',
        compute='_compute_sub_partner_ids',
    )

    @api.depends('partner_id')
    def _compute_sub_partner_ids(self):
        for item in self:
            item.sub_partner_ids = item.partner_id.sub_provider_ids.ids 

    sub_provider_id = fields.Many2one(
        'res.partner', string='Sub-Proveedor', domain="[('id', 'in', sub_partner_ids)]"
    )
    
    #Informacion de Importaciones
    bl_number = fields.Char(
        string='Número de BL',
    )

    date_shipment = fields.Datetime(
        string='Fecha de Embarque',
    )

    date_departure = fields.Datetime(
        string='Fecha de Zarpe',
    )

    date_arrival_port = fields.Datetime(
        string='Fecha de Llegada a Puerto',
    )

    date_arrival_warehouse = fields.Datetime(
        string='Fecha de Llegada al Almacén',
    )

    def _domain_payment_term_user(self):
        payment_term_user = self.env.user.payment_term_ids.ids or []
        return [('id', '=', payment_term_user),('company_id', '=', self.company_id.id)]

    payment_term_id = fields.Many2one(
        'account.payment.term', 
        'Payment Terms', 
        domain=_domain_payment_term_user)

    approvals_approver_ids = fields.Many2many(
        'approval.approver', 
        string='Aprobaciones', 
        compute='_compute_approvals_approver_ids',
    )

    update_tax_today = fields.Boolean(
        string='Cambiar Tasa ',
        tracking=True,
        help="Este check permite usar la tasa de la fecha seleccionada."
    )

    @api.depends('approvals_ids')
    def _compute_approvals_approver_ids(self):
        for rec in self:
            rec.approvals_approver_ids = []
            if len(rec.approvals_ids) >= 1:
                rec.approvals_approver_ids = rec.approvals_ids.mapped('approver_ids')
                
    def approvals_request_purchase(self):
        for purchase in self:
            if purchase.is_approval and not purchase.order_line:
                raise UserError(
                    "No puede enviar una orden de compra sin lineas de pedidos. Por favor agregue lineas a la orden")
            approvers = len(purchase.approver_ids)
            category_obj = self.env['approval.category'].search([('is_purchase', '=', 'required'),('company_id', '=', purchase.company_id.id)], limit=1)
            if not category_obj:
                raise ValidationError("No existe una categoría de aprobación configurada para pedidos de compra.")
                
            for aproval in purchase.approvals_ids:
                if aproval.request_status in ['new', 'pending', 'approved']:
                    raise ValidationError("Existe una aprobacion en curso")
                if aproval.request_status == "refused":
                    raise ValidationError("Verifique si no existe una solicitud Rechazada antes de generar una nueva")
            
            for apr in purchase.approver_ids:
                if purchase.amount_total >= apr.approving_amount:
                    state=True
                    break
                if apr.approving_amount >= purchase.amount_total:
                    state=False
                    break
                    
            approval_request = self.env['approval.request'].create({
                'name': f'{category_obj.name} - {purchase.name}',
                'category_id': category_obj.id,
                'date': datetime.now(),
                'request_owner_id': purchase.env.user.id,
                'reference': purchase.partner_ref,
                'partner_id': purchase.partner_id.id,
                'amount_purchase': purchase.amount_total,
                'approving_amount': apr.approving_amount,
                'next_approver_ids': purchase.approver_ids.approving_leader_oc_ids.ids,
                'is_next_approver': state,
                'purchase_id': purchase.id,
                'request_status': 'pending'
            })

            for item in purchase.approver_ids:
                self.env['approval.approver'].create({
                    'user_id': item.id,
                    'request_id': approval_request.id,
                    'status': 'pending'
            })
            approval_request.action_confirm()
            
            if not category_obj:
                raise ValidationError(
                    "No existe una categoría de aprobación para este tipo de registro."
                     "Vaya a Aprobaciones / Configuración / Tipo de aprobación.")
            if len(category_obj) > 2:
                raise ValidationError(
                    "Existe mas de dos categoría de aprobación para este tipo de registro."
                     "Vaya a Aprobaciones / Configuración / Tipo de aprobación.")

    def is_possible_confirm(self):
        for rec in self:
            return True if rec.approvals_approver_ids.filtered(lambda x: x.required and x.status != 'approved' and x.request_id.request_status != 'cancel') else False

    def button_confirm(self):
        for rec in self:
            if rec.is_approval:
                if not rec.approvals_ids or not rec.approvals_ids.filtered(lambda l: l.request_status in ['new','pending','approved']):
                    raise ValidationError("Disculpe!!! Debe solicitar aprobación.")
                else:
                    if self.is_possible_confirm():
                        raise ValidationError("Existen aprobadores requeridos pendientes por aprobar.")
                    elif not rec.approvals_ids.filtered(lambda l: l.request_status == 'approved'):
                        raise ValidationError("Existen aprobaciones pendientes.")
        return super(PurchaseOrder, self).button_confirm()

    @api.depends('is_approval')
    def _compute_approver(self):
        for rec in self:
            category_obj = self.env['res.users'].search([('id', '=', self.env.uid)], limit=1)
            if category_obj:
                rec.approver_ids = category_obj.approving_leader_oc_ids.ids
            if not category_obj.user_ids:
                raise ValidationError(
                    "Disculpe no tiene Aprobadores Configurados"
                    "Vaya a Aprobaciones / Configuración / Tipo de aprobación.")
    
    def _Compute_approval_progress(self):
        for rec in self:            
            request = self.env['approval.request'].search([('purchase_id', '=', self.id),('company_id', '=', rec.company_id.id)], limit=1).id
            if not request:
                rec.is_approval_progress = False
            else:
                rec.is_approval_progress = True

    def _prepare_invoice(self):
        invoice_vals = super(PurchaseOrder, self)._prepare_invoice()
        invoice_vals.update({
            'tax_today': self.tax_today,
            'sub_provider_id': self.sub_provider_id.id,
        })
        return invoice_vals

    def button_cancel(self):
        res = super(PurchaseOrder, self).button_cancel()
        for rec in self:
            if rec.approvals_ids:
                for approval in rec.approvals_ids.filtered(lambda l: l.request_status != 'cancel'):
                    approval.write({'request_status': 'cancel'})
                    for approver in approval.approver_ids:
                        approver.write({'status': 'cancel'})
        return res

    @api.onchange('update_tax_today', 'date_order')
    def _chage_tax(self):
        for rec in self:
            if rec.update_tax_today:
                tax_changed = 0.0
                tax = self.env['res.currency.rate'].search([('currency_id', '=', rec.currency_id.id),('company_id', '=', self.env.company.id),('name', '=', rec.date_order.date())])
                tax_changed = 1/tax.rate if tax.rate else 0.0
                if tax_changed:
                    rec.tax_today = tax_changed
            else:
                rec.tax_today = self.env.company.currency_id_dif.inverse_company_rate