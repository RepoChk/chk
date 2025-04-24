# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from dateutil.relativedelta import relativedelta

import logging

_logger = logging.getLogger(__name__)

class WarrantyRequest(models.Model):
    _name = 'warranty.request'
    _description = 'Solicitud de garantia'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc, id desc'

    name = fields.Char(string='Título', required=True, readonly=True, copy=False, default='/')

    description = fields.Char(
        string='Descripción',
        tracking=True,
        required=True,
    )
    
    technical_ids = fields.Many2many(
        'res.users', 
        'warranty_res_user_rel', 
        'technical_id', 
        'users_id', 
        string='Tecnicos', 
        tracking=True, 
        change_default=True, 
    )

    state = fields.Selection([
        ('draft', "Borrador"), 
        ('confirm', "Confirmar"), 
        ('process', "En proceso"), 
        ('done', "Finalizado"), 
        ('refused', "Rechazado"),
        ], default='draft', required=True, tracking=True,)
    
    product_type = fields.Selection([
        ('bateria', "Batería"), 
        ('neumatico', "Neumático"),
        ], string='Tipo de producto', required=True,)

    observation = fields.Text(
        string='Observación',
        tracking=True,
    )

    reason = fields.Text(
        string='Razón de llenado manual',
        tracking=True,
    )

    lot_ids = fields.Many2many('stock.lot', string='Lotes', compute='_compute_lot_ids', store=False)

    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id.id
    )

    amount_nc = fields.Monetary('Monto', currency_field='currency_id')

    @api.depends('product_id')
    def _compute_lot_ids(self):
        for rec in self:
            if rec.product_id and rec.state == 'draft':
                # Buscar todos los lotes asociados al producto seleccionado
                lot_ids = self.env['stock.lot'].search([
                    ('product_id.product_tmpl_id', '=', rec.product_id.id)
                ])
                rec.lot_ids = lot_ids
            else:
                rec.lot_ids = False  # Limpiar si no hay producto seleccionado

    lot_id = fields.Many2one(
        'stock.lot',
        string='Serial - Seguimiento',
        domain="[('id', '=', lot_ids)]"
    )
    
    tracking_number = fields.Char(
        string='Seguimiento',
        related='lot_id.tracking_number'
    )

    product_ids = fields.Many2many(
        'product.template',
        compute='_compute_product_ids'
    )

    @api.depends('product_type')
    def _compute_product_ids(self):
        for rec in self:
            domain = [('is_warranty', '=', True),('is_battery', '=', False)]
            if rec.product_type == 'bateria':
                domain = [('is_warranty', '=', True),('is_battery', '=', True)]
            rec.product_ids = self.env['product.template'].search(domain).ids

    def _get_domain_produc_id(self):
        domain = [('is_warranty','=',True),]
        for rec in self:
            if rec.product_type == 'bateria':
                domain = [
                    ('is_battery','=',True),
                    ('is_warranty','=',True),
                ]
        return domain

    product_id = fields.Many2one(
        'product.template',
        string='Producto',
        domain="[('id','in',product_ids), ]"
    )

    is_reposition_product = fields.Boolean(
        string='Usar Producto de Reposición',
    )

    reposition_product_id = fields.Many2one(
        'product.template',
        string='Producto de Reposición',
    )
    

    invoice_id = fields.Many2one(
        'account.move',
        string='Factura',
        domain="[('id', 'in', invoice_ids)]",
    )

    invoice_ids = fields.Many2many(
        'account.move',
        string='Factura',
        compute='_compute_datas',
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        related='invoice_id.partner_id',
        store=True,
        readonly=False,
        domain="[('company_id','in',(False, company_id)), ]"
    )

    seller_id = fields.Many2one(
        'res.users',
        string='Vendedor',
        related='invoice_id.invoice_user_id',
        store=True,
        readonly=False, 
    )

    is_battery = fields.Boolean(
        related='product_id.is_battery',
    )

    is_manual = fields.Boolean(
        string='¿Llenado manual?',
    )

    manual = fields.Boolean()

    percentage = fields.Integer(
        string='Porcentaje',
    )

    schedule_date = fields.Date(
        string='Fecha prevista'
    )

    invoice_date = fields.Date(
        string='Fecha factura',
        related='invoice_id.invoice_date',
        store=True,
        tracking=True,
    )

    date = fields.Date(
        string='Fecha de solicitud',
        default=fields.Date.context_today,
        readonly=True, 
    )

    date_sale = fields.Date(
        string='Fecha de venta', 
        index=True, 
        compute='_compute_date_sale',
        store=True,
    )

    approvals_ids = fields.One2many('approval.request', 'warranty_id', string='Aprobaciones')
    approver_ids = fields.Many2many('res.users', string='Aprobadores', readonly=True, compute='_compute_approver', store=True)
    is_approval = fields.Boolean(string="Tiene aprobación", default=True,)

    duration = fields.Float(
        string='Duración',
    )

    company_id = fields.Many2one(
        'res.company', 
        string='Compañía', 
        default=lambda self: self.env.company, 
        required=True, 
        readonly=True,
    )

    warranty_period = fields.Integer(
        string='Periodo de garantía',
        related='product_id.warranty_period'
    )

    user_id = fields.Many2one('res.users', string='Usuario', default=lambda self: self.env.uid)

    total_months = fields.Integer(string='Meses desde la venta', compute='_compute_total_months')

    approval_send = fields.Boolean(default=False, compute="_compute_approvals",)

    approval_accepted = fields.Boolean(default=False, compute="_compute_approvals",)

    nc_id = fields.Many2one(
        'account.move',
        string='Nota de Crédito',
        readonly=True, 
    )

    sale_order_ids = fields.One2many(
        'sale.order',
        'warranty_id',
        string='Orden de Venta',
    )

    sale_count = fields.Integer(
        string='Contador de ventas', compute='_compute_sale_ids'
    )

    approvals_approver_ids = fields.Many2many('approval.approver', string='Aprobaciones', compute='_compute_approvals_approver_ids')

    @api.depends('approvals_ids')
    def _compute_approvals_approver_ids(self):
        for rec in self:
            rec.approvals_approver_ids = []
            if len(rec.approvals_ids) >= 1:
                rec.approvals_approver_ids = rec.approvals_ids.mapped('approver_ids')

    @api.depends('sale_order_ids')
    def _compute_sale_ids(self):
        for item in self:
            sale_order = self.env['sale.order'].search([
                ('warranty_id', '=', item.id)
            ])
            item.sale_count = len(sale_order)
            
    @api.depends('approvals_ids')
    def _compute_approvals(self):
        for record in self:
            record.approval_send = bool(record.approvals_ids.filtered(lambda l: l.request_status == 'pending'))
            record.approval_accepted = bool(record.approvals_ids.filtered(lambda l: l.request_status == 'approved'))


    @api.depends('date_sale', 'date')
    def _compute_total_months(self):
        for record in self:
            total = 0
            if record.date_sale and record.date:
                fecha_inicio = fields.Date.from_string(record.date_sale)
                fecha_fin = fields.Date.from_string(record.date)
                diferencia = relativedelta(fecha_fin, fecha_inicio)
                total = diferencia.years * 12 + diferencia.months
            periodo = record.warranty_period or 0
            record.total_months = (periodo - total)

    @api.constrains('date_sale', 'invoice_date', 'date')
    def _check_dates(self):
        for line in self:
            if line.date_sale and line.invoice_date:
                if line.date_sale < line.invoice_date:
                    raise UserError(_('La fecha de venta no puede ser menor a la fecha de la factura'))
                if line.date_sale > line.date:
                    raise UserError(_('La fecha de venta no puede ser mayor a la fecha de solicitud'))

    @api.depends('invoice_id', 'invoice_date')
    def _compute_date_sale(self):
        for rec in self:
            if not rec.invoice_id:
                rec.date_sale = False
            rec.date_sale = rec.invoice_id.invoice_date

    @api.depends('partner_id','seller_id','product_id')
    def _compute_datas(self):
        for rec in self:
            domain = [('state', '=', 'posted'), ('move_type', '=', 'out_invoice')]
            
            if rec.partner_id:
                domain.append(('partner_id', '=', rec.partner_id.id))
            if rec.seller_id:
                domain.append(('invoice_user_id', '=', rec.seller_id.id))
            if rec.product_id:
                domain.append(('invoice_line_ids.product_id.product_tmpl_id', '=', rec.product_id.id))
            
            ids = self.env['account.move'].sudo().search(domain, limit=100).ids
            rec.invoice_ids = ids if len(ids) >= 1 else []

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        for rec in self:
            if not rec.lot_id:
                rec.invoice_id = False
                rec.partner_id = False
                rec.seller_id = False
                rec.invoice_date = False
            else:
                rec.product_id = rec.lot_id.product_id.product_tmpl_id.id

    def _get_or_create_sequence(self):
        company_name = self.env.company
        sequence_code = f'warranty_{company_name.id}'

        sequence = self.env['ir.sequence'].search([('code', '=', sequence_code)], limit=1)
        
        if not sequence:
            sequence = self.env['ir.sequence'].create({
                'name': f'Secuencia para garantías {self.env.company.name}',
                'code': sequence_code,
                'implementation': 'standard',
                'prefix': 'GA-',
                'padding': 6,
                'number_next': 1,
                'number_increment': 1,
            })
        
        return sequence

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            sequence = self._get_or_create_sequence()
            vals['name'] = sequence.next_by_id()
        return super(WarrantyRequest, self).create(vals)
    
    @api.depends('is_approval')
    def _compute_approver(self):
        for record in self:
            category_obj = self.env['approval.category'].search([('company_id', '=', self.company_id.id),('is_warranty', '!=', 'no')], limit=1)
            if category_obj:
                approvers = category_obj.approver_ids
                user_ids = approvers.mapped('user_id')
                record.approver_ids = [(6, 0, user_ids.ids)]
            else:
                record.approver_ids = [(5, 0, 0)]
                raise ValidationError(
                    "No se encontró una categoría de aprobación para garantías. "
                    "Por favor, configure una categoría en Aprobaciones / Configuración / Tipo de aprobación.")

    def approvals_request_warranty(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Solicitud de aprobación"),
            'target': 'new',
            'res_model': 'gc.approval.request.wizard',
            'view_mode': 'form',
            'context': {
                'warranty_request_id': self.id,
            },
        }

    def _get_warranty_order_user_id(self):
        user = self.env['ir.config_parameter'].sudo().get_param('gc_warranty.warranty_order_user_id')
        return user

    def _get_warranty_close_user_id(self):
        user = self.env['ir.config_parameter'].sudo().get_param('gc_warranty.warranty_close_user_id')
        return user

    def is_possible_confirm(self):
        for rec in self:
            return True if rec.approvals_approver_ids.filtered(lambda x: x.required and x.status != 'approved' and x.request_id.request_status != 'cancel') else False

    def button_process(self):
        if self.is_possible_confirm():
            raise ValidationError("Existen aprobadores requeridos pendientes por aprobar.")
        for rec in self:
            if rec.is_approval:
                if not rec.approval_accepted:
                    raise ValidationError("No Puede pasar a 'PROCESO' si no esta aprobado")
            rec.state = 'process'

    def button_draft(self):
        for rec in self:
            if rec.approvals_ids:
                for approval in rec.approvals_ids.filtered(lambda l: l.request_status != 'cancel'):
                    approval.write({'request_status': 'cancel'})
                    for approver in approval.approver_ids:
                        approver.write({'status': 'cancel'})
            rec.state = 'draft'

    def button_refused(self):
        self.state = 'refused'

    def button_done(self):
        self.state = 'done'

    def button_confirm(self):
        self.state = 'confirm'

    def action_send_approval(self):
        for warranty in self:
            if warranty.approvals_ids.filtered(lambda r: r.request_status in ['new', 'pending', 'approved']):
                raise ValidationError("Existe una aprobación en curso o ya fue aprobado")

            category_obj = self.env['approval.category'].search([('is_warranty', '!=', 'no'),('company_id', '=', warranty.company_id.id)], limit=1)
            if not category_obj:
                raise ValidationError("No existe una categoría de aprobación configurada para Garantías.")
            
            approval_request = self.env['approval.request'].create({
                'name': f'{category_obj.name} - {warranty.name}',
                'category_id': category_obj.id,
                'date': datetime.now(),
                'request_owner_id': warranty.env.user.id,
                'partner_id': warranty.partner_id.id,
                'warranty_id': warranty.id,
            })
            approval_request.action_confirm()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Aprobación Registrada'),
                'message': _('La solicitud de aprobación se ha registrado correctamente.'),
                'sticky': False,  # Si es True, la notificación no desaparece hasta que el usuario la cierre
                'next': {
                    'type': 'ir.actions.act_window_close',
                }
            }
        }

    def action_manual_wizard(self):
        self.ensure_one()
        return {
            'name': 'Seleccionar la factura',
            'type': 'ir.actions.act_window',
            'res_model': 'manual.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_seller_id': self.seller_id.id,
                'default_product_id': self.product_id.id,
                'default_warranty_id': self.id,
                'default_product_type': self.product_type,
            },
        }

    @api.onchange('is_manual')
    def _onchange_is_manual(self):
        for rec in self:
            rec.lot_id = False
            rec.manual = False
            rec.product_id = False
            rec.invoice_id = False
            rec.partner_id = False
            rec.seller_id = False
            rec.invoice_date = False

    def prepare_invoice(self):
        # Aca preparamos los valores de la nota de credito
        self.ensure_one()
        
        invoice_line_vals = [(0, 0, {
            'product_id': self.reposition_product_id.product_variant_id.id if self.is_reposition_product else self.product_id.product_variant_id.id,
            'name': f"Devolución por garantía: {self.name} - {self.product_id.name}",
            'quantity': 1,
            'price_unit': self.amount_nc,
            'product_uom_id': self.reposition_product_id.uom_id.id if self.is_reposition_product else self.product_id.uom_id.id,
        })]

        values = {
            'move_type': 'out_refund',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.context_today(self),
            'ref': f"Devolución por garantía: {self.name}",
            'invoice_line_ids': invoice_line_vals,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'warranty_id': self.id,
            'narration': self.description,
            'reversed_entry_id_new': self.invoice_id.id,
            'invoice_user_id': self.invoice_id.invoice_user_id.id,
            'team_id': self.invoice_id.team_id.id,
            'branch_id': self.invoice_id.branch_id.id,
        }
        
        return values

    def apply_credit_note(self):
        self.ensure_one()
        return {
            'name': 'Aplicar nota de Crédito',
            'type': 'ir.actions.act_window',
            'res_model': 'apply.credit.note.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_warranty_id': self.id,
                'default_refund_values': self.prepare_invoice(),
            },
        }

    def action_view_sale(self):
        self.ensure_one()
        # Obtener las órdenes de venta relacionadas
        sales = self.sale_order_ids
        
        # Definir la acción
        action = {
            'name': 'Órdenes de Venta',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'context': {'create': False},
        }
        
        if len(sales) == 1:
            # Si solo hay una orden, mostrar el formulario directamente
            action.update({
                'view_mode': 'form',
                'res_id': sales.id,
            })
        else:
            # Si hay múltiples órdenes, mostrar la lista
            action.update({
                'domain': [('id', 'in', sales.ids)],
            })
        
        return action