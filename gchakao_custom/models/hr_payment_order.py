# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json

class HrPaymentOrder(models.Model):
    _name = 'hr.payment.order'
    _inherit = ['mail.thread','mail.activity.mixin']
    _description = 'Orden de pago en Nómina'
    _order = 'date desc, name desc, id desc'

    name = fields.Char(string='Nombre', required=True, readonly=True, copy=False, default='/')
    employee_id = fields.Many2one('hr.employee', string='Empleado',)
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Lote',)
    payslip_id = fields.Many2one('hr.payslip', string='Recibo de Pago',)
    payslip_ids = fields.Many2many('hr.payslip', string='Recibos de Pago', compute='_compute_payslip_ids')
    payment_id = fields.Many2one('account.payment', string='Pago', readonly=True)
    journal_id = fields.Many2one('account.journal', string='Diario', tracking=True)
    amount_usd = fields.Monetary(string='Monto USD', readonly=False, currency_field='currency_id_dif',)
    amount_bs = fields.Monetary(string='Monto', compute='_compute_amount', readonly=False, store=True, currency_field='currency_id_company',)
    rate = fields.Float(string='Tasa', related='payslip_id.tasa_cambio', store=True, readonly=False, default=lambda self: self._get_default_tasa_cambio(), tracking=True, digits='Dual_Currency_rate')
    hr_discount_type_id = fields.Many2one('hr.discount.type', string='Tipo descuento',)
    type_payment_order = fields.Selection([
        ('loan', 'Prestamo'),
        ('payslip', 'Nómina'),
        ('discount', 'Descuento'),
        ('other', 'Otros'),
    ], string='Tipo', default='payslip')

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirm', 'Confirmado'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('done', 'Hecho'),
    ], string='Estado', default='draft', tracking=True)

    currency_id_dif = fields.Many2one("res.currency",
                                      string="Divisa de Referencia",
                                      default=lambda self: self.env.company.currency_id_dif)
    currency_id_company = fields.Many2one("res.currency",
                                          string="Divisa compañía",
                                          default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one("res.company", string="Compañía", default=lambda self: self.env.company, readonly=True, store=True,)
    is_approval = fields.Boolean(
        string="Tiene aprobación", 
        default=True,
        tracking=True,
    )

    date = fields.Date(string="Fecha de Solicitud", default=fields.Date.today, readonly=True, )
    date_payment = fields.Date(string="Fecha de Pago")

    observation = fields.Text(
        string='Observación',
        tracking=True,
    )

    c_approvals_ids = fields.One2many('approval.request', 'payment_order_id', string='Solicitud de Aprobaciones')
    c_approver_ids = fields.Many2many('res.users', string='Aprobadores', readonly=True, compute='_compute_approver', store=True)
    c_approvals_approver_ids = fields.Many2many('approval.approver', string='Aprobaciones', compute='_compute_c_approvals_approver_ids')

    @api.depends('c_approvals_ids')
    def _compute_c_approvals_approver_ids(self):
        for rec in self:
            rec.c_approvals_approver_ids = []
            if len(rec.c_approvals_ids) >= 1:
                rec.c_approvals_approver_ids = rec.c_approvals_ids.mapped('approver_ids')

    @api.depends('amount_usd','rate')
    def _compute_amount(self):
        for rec in self:
            amount_bs = 0
            if rec.amount_usd > 0 and rec.rate > 0:
                amount_bs = rec.amount_usd * rec.rate
            rec.amount_bs = amount_bs

    def _get_or_create_sequence(self):
        company_name = self.env.company.name.replace(" ", "")
        sequence_code = f'{company_name[:6]}_hr_payment_order'

        sequence = self.env['ir.sequence'].search([('code', '=', sequence_code)], limit=1)
        
        if not sequence:
            sequence = self.env['ir.sequence'].create({
                'name': f'Secuencia para {self.env.company.name}',
                'code': sequence_code,
                'implementation': 'standard',
                'prefix': 'OPN',
                'padding': 5,
                'number_next': 1,
                'number_increment': 1,
                'company_id': self.company_id.id,
            })
        
        return sequence

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            sequence = self._get_or_create_sequence()
            vals['name'] = sequence.next_by_id()
        return super(HrPaymentOrder, self).create(vals)


    @api.depends('is_approval')
    def _compute_approver(self):
        for rec in self:
            category_obj = self.env['approval.category'].search([('is_order_payment', '!=', 'no'),('company_id', '=', rec.company_id.id)], limit=1)
            if category_obj:
                rec.c_approver_ids = category_obj.approver_ids.user_id.ids
            elif category_obj and not category_obj.approver_ids:
                raise ValidationError(
                    "Disculpe no tiene Aprobadores Configurados"
                    "Vaya a Aprobaciones / Configuración / Tipo de aprobación.")

    def action_send_approval(self):
        for rec in self:
            # Verificar si ya existe una aprobación en curso o aprobada
            if rec.c_approvals_ids.filtered(lambda r: r.request_status in ['new', 'pending']):
                raise ValidationError("Existe una aprobación en curso")

            # Buscar la categoría de aprobación para pedidos de ventas
            category_obj = self.env['approval.category'].search([('is_order_payment', '!=', 'no'),('company_id', '=', rec.company_id.id)], limit=1)
            if not category_obj:
                raise ValidationError("No existe una categoría de aprobación configurada para pedidos de ventas.")

            # Crear la solicitud de aprobación
            approval_request = self.env['approval.request'].create({
                'name': f'{category_obj.name} - {rec.name}',
                'category_id': category_obj.id,
                'date': fields.Datetime.now(),
                'request_owner_id': self.env.user.id,
                'payment_order_id': rec.id,
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

    def _get_default_tasa_cambio(self):
        dolar = self.env['res.currency'].search([('name', '=', 'USD')])
        tasa = dolar.inverse_company_rate
        for rec in self:
            if rec.payslip_run_id:
                if rec.payslip_run_id.tasa_cambio:
                    if rec.payslip_run_id.tasa_cambio > 0:
                        tasa = rec.payslip_run_id.tasa_cambio
        return tasa

    def action_confirm(self):
        self.state = 'confirm'
        if self.payslip_id:
            self.payslip_id.payment_order_id = self.id

    def action_draft(self):
        for rec in self:
            if rec.payment_id:
                payment = rec.payment_id
                if payment.state == 'draft':
                    payment.action_cancel()
                    payment.unlink()
                elif payment.state == 'posted':
                    raise UserError('No se puede pasar a borrador, el pago ya está validado.')
            rec.state = 'draft'
            if rec.c_approvals_ids:
                for approval in rec.c_approvals_ids.filtered(lambda l: l.request_status != 'cancel'):
                    approval.write({'request_status': 'cancel'})
                    for approver in approval.approver_ids:
                        approver.write({'status': 'cancel'})

    def action_done(self):
        for rec in self:
            rec.state = 'done'

    def action_rejected(self):
        for rec in self:
            rec.state = 'rejected'
    
    def is_possible_create_payment(self):
        for rec in self:
            return True if rec.c_approvals_approver_ids.filtered(lambda x: x.required and x.status != 'approved' and x.request_id.request_status != 'cancel') else False

    def action_create_payment(self):
        if self.is_possible_create_payment():
            raise UserError('No se puede generar el pago, existen aprobaciones pendientes')
        for rec in self:
            if not rec.journal_id:
                raise UserError(f'Disculpe, debe seleccionar el Diario')
            if not rec.employee_id.work_contact_id:
                raise UserError(f'El empleado {rec.employee_id.name} no tiene un contacto relacionado')
            if not rec.employee_id.work_contact_id.property_account_payable_id:
                raise UserError(f'El contacto {rec.employee_id.work_contact_id.name} no tiene un asignada una cuenta por pagar')

            # Obtener la cuenta analítica del contrato del empleado
            analytic_account_id = rec.employee_id.contract_id.analytic_account_id.id

            # Distribución analítica para el pago
            analytic_distribution = {
                analytic_account_id: 100.0  # 100% del monto del pago asignado a esta cuenta analítica
            }

            # CUANDO ES UNA ORDEN DE PAGO GENERADA DESDE UN RECIBO DE PAGO SE TOMA EL DIARIO DE LA ESTRUCTURA DE NOMINA
            destination_account = rec.employee_id.work_contact_id.property_account_payable_id.id if not rec.payslip_id else rec.payslip_id.struct_id.journal_id.default_account_id.id
            if not destination_account:
                raise UserError(f'Revise lo siguiente:\n -El contacto del trabajador ubicado en Empleado/ Ajustes de RR. HH./ Contacto de trabajo/ Contabilidad\n -Recibo de pagpo/ Estructura/ Diario de salario')
            amount = rec.amount_usd if rec.journal_id.currency_id.id != rec.journal_id.company_id.currency_id.id else rec.amount_bs
            amount_local = rec.amount_bs
            amount_ref = rec.amount_usd
            payment_vals = {
                'amount': amount,
                'amount_ref': amount_ref,
                'amount_local': amount_local,
                'currency_id': rec.journal_id.currency_id.id,
                'payment_type': 'outbound',
                'partner_id': rec.employee_id.work_contact_id.id,
                'journal_id': rec.journal_id.id,
                'tax_today': rec.rate,
                'from_payment_order': True,
                'hr_payment_order_id': rec.id,
                'state': 'draft',
                'partner_type': 'supplier',
                'destination_account_id': destination_account,
                'outstanding_account_id': rec.journal_id.default_account_id.id,
                'ref': rec.payslip_id.display_name,
                # 'analytic_distribution': analytic_distribution,
            }
            # Crear el pago en borrador con los valores
            payment = self.env['account.payment'].create(payment_vals)
            if payment:
                payment.send_notification_account_payment(self.name)
                rec.payment_id = payment.id

    def _get_hr_payment_order_notification_user_id(self):
        user = self.env['ir.config_parameter'].sudo().get_param('gchakao_custom.hr_payment_order_notification_user_id')
        return user

    def action_approve(self):
        self.state = 'approved'
        activity_type_id = self.env.ref('gchakao_custom.mail_activity_type_alert_hr_payment_order').id
        user = self._get_hr_payment_order_notification_user_id()
        self.activity_schedule(
            activity_type_id=activity_type_id,
            user_id=user,
            note="La orden de pago {} esta pendiente por generar pago.".format(self.name),
        )

    @api.onchange('payslip_id')
    def _onchange_payslip(self):
        for rec in self:
            if rec.payslip_id:
                rec.employee_id = rec.payslip_id.employee_id

    @api.depends('employee_id', 'payslip_run_id')
    def _compute_payslip_ids(self):
        for rec in self:
            if not rec.employee_id and not rec.payslip_run_id:
                rec.payslip_ids = []
                continue

            payslip_ids = []
            domain = [('company_id', '=', rec.company_id.id)]
            if rec.employee_id:
                domain.append(('employee_id', '=', rec.employee_id.id))
            if rec.payslip_run_id:
                domain.append(('payslip_run_id', '=', rec.payslip_run_id.id))
            
            payslip_ids = self.env['hr.payslip'].search(domain).ids or []
            rec.payslip_ids = payslip_ids
