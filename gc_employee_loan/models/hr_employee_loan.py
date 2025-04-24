# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta, time

class HREmployeeLoan(models.Model):
    _name = 'hr.employee.loan'
    _description = 'Presamos de Empleados'
    _inherit = ['mail.thread', 'portal.mixin']
    _order = 'name desc'

    loan_state=[('draft','Borrador'),
                ('request','Solicitar'),
                ('dep_approval','Aprobado por Jefe de Departamento'),
                ('hr_approval','Aprobado por Jefe de Recursos Humanos'),
                ('paid','Pagado'),
                ('done','Hecho'),
                ('close', 'Cerrado'),
                ('reject','Rechazado'),
                ('cancel','Cancelado')]
                
    @api.model
    def _get_employee(self):
        employee_id = self.env['hr.employee'].search([('user_id','=',self.env.user.id)],limit=1)
        return employee_id

    def _get_employee_domain(self):
        return [('company_id', '=', self.company_id.id)]

    @api.model
    def _get_default_user(self):
        return self.env.user

    def send_loan_detail(self):
        if self.employee_id and self.employee_id.work_email:
            template_id = self.env['ir.model.data'].get_object_reference('l10n_ve_payroll', 'dev_HREmployeeLoan_detail_send_mail')

            template_id = self.env['mail.template'].browse(template_id[1])
            template_id.send_mail(self.ids[0], True)
        return True
        
    @api.depends('installment_lines')
    def _get_end_date(self):
        for loan in self:
            end_date = False
            if loan.installment_lines:
                # Obtener la fecha de la última cuota
                end_date = max(installment.date for installment in loan.installment_lines)
            loan.end_date = end_date

    @api.depends('installment_lines','paid_amount')
    def get_extra_interest(self):
        for loan in self:
            amount = 0
            for installment in loan.installment_lines:
                if installment.is_skip:
                    amount += installment.ins_interest
            loan.extra_in_amount = amount

    name = fields.Char('Nombre', default='/', copy=False)
    state = fields.Selection(loan_state,string='Estatus',default='draft', track_visibility='onchange')
    employee_id = fields.Many2one('hr.employee', default=_get_employee, required=True, string='Empleado')
    department_id = fields.Many2one('hr.department',string='Departamento')
    hr_manager_id = fields.Many2one('hr.employee',string='Jefe de Recursos Humanos')
    manager_id = fields.Many2one('hr.employee',string='Jefe de Departamento', required=True)
    job_id = fields.Many2one('hr.job',string="Cargo")
    date = fields.Date('Fecha',default=fields.Date.today())
    start_date = fields.Date('Fecha de inicio',default=fields.Date.today(),required=True)
    end_date = fields.Date('Fecha fin',compute='_get_end_date')
    term = fields.Integer('Cuotas', default=1)
    loan_type_id = fields.Many2one('hr.employee.loan.type',string='Tipo de prestamo')
    loan_amount = fields.Monetary('Monto del prestamo',required=True, currency_field='currency_id_dif')
    paid_amount = fields.Monetary('Monto pagado',compute='get_paid_amount', currency_field='currency_id_dif')
    remaing_amount = fields.Monetary('Monto restante', compute='get_remaing_amount', currency_field='currency_id_dif')
    installment_amount = fields.Monetary('Monto de cuota',required=True, compute='get_installment_amount', currency_field='currency_id_dif')
    loan_url = fields.Char('URL', compute='get_loan_url')
    user_id = fields.Many2one('res.users',default=_get_default_user)
    is_apply_interest = fields.Boolean('Aplicar Interes', default=False)
    interest_type = fields.Selection([('liner', 'Linear'), ('reduce', 'Reducido')], string='Tipo de Interes',
                                     default='liner')
    interest_rate = fields.Float(string='% Intereses', default=10)
    interest_amount = fields.Monetary('Monto de intereses', currency_field='currency_id_dif')
    installment_lines = fields.One2many('hr.employee.loan.installment.line','loan_id',string='Cuotas')
    notes = fields.Text('Razón', required=True)
    is_close = fields.Boolean('Cerrado',compute='is_ready_to_close')
    move_id = fields.Many2one('account.move',string='Asiento Contable')
    loan_document_line_ids = fields.One2many('hr.employee.loan.document','loan_id')
    installment_count = fields.Integer(compute='get_interest_count')
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    currency_id_dif = fields.Many2one('res.currency', string='Moneda', related='company_id.currency_id_dif')

    journal_id = fields.Many2one('account.journal',string='Diario',)
    gc_loan_type_id = fields.Many2one('gc.hr.employee.loan.type', string='Típo de préstamo')
    loan_account = fields.Many2one('account.account', string='Cuenta de Prestamo', required=True, related='gc_loan_type_id.account_id')

    # struct_type_id = fields.Many2one('hr.payroll.structure.type', string='Tipo de Nómina',)
    # struct_id = fields.Many2one('hr.payroll.structure', string='Nómina', domain="[('type_id','=',struct_type_id), ]")
    # period = fields.Selection(related='struct_type_id.default_schedule_pay', string='Periodo', store=True)
    
    generate_payment_order = fields.Boolean(
        string='Generar pago',
        help='Para préstamos que ya fueron desembolsados se debe desmarcar esta opción ya que se duplicarian los saldos\nSolo se van a generar asientos por las cuotas que se descuenten a los empleados', 
        default=True,
    )

    hr_payment_type = fields.Selection([
        ('percentage', 'Porcentaje'),
        ('quota', 'Cuotas')
    ], string='Tipo de Pago', default='quota', required=True)

    period = fields.Selection([
        ('bi-weekly', 'Quincenal'),
        ('monthly', 'Mensual')
    ], string='Periodo de Pago', default='bi-weekly', required=True)

    # loan_type = fields.Selection([
    #     ('monetary', 'Monetario'),
    #     ('bien', 'Bienes')
    # ], string='Tipo de Prestamo', default='monetary', required=True)

    payment_order_id = fields.Many2one(
        'hr.payment.order',
        string='Orden de Pago',
        readonly=True,
    )

    payment_order_state = fields.Selection(related='payment_order_id.state')

    # is_percentage = fields.Boolean(
    #     string='Basado en porcentaje',
    # )

    # percentage = fields.Float(
    #     string='Porcentaje',
    #     default=0.3,
    # )

    @api.onchange('employee_id')
    def change_employee_id(self):
        for rec in self:
            if rec.employee_id:
                # Buscar préstamos no cerrados, no rechazados o no cancelados en la compañía actual
                disable = self.env['hr.employee.loan'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', 'not in', ['close', 'reject', 'cancel']),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                
                if disable:
                    raise UserError(f'El empleado {rec.employee_id.name} tiene préstamos en proceso de pago o en borrador.')
                else:
                    # Llenar los campos con la información correspondiente
                    rec.department_id = rec.employee_id.department_id.id if rec.employee_id.department_id else False
                    rec.manager_id = rec.employee_id.department_id.manager_id.id if rec.employee_id.department_id and rec.employee_id.department_id.manager_id else rec.employee_id.parent_id.id if rec.employee_id.parent_id else False
                    rec.job_id = rec.employee_id.job_id.id if rec.employee_id.job_id else False
            else:
                # Limpiar campos si no hay empleado seleccionado
                rec.department_id = False
                rec.manager_id = False
                rec.job_id = False

    def payment_vals(self):
        self.ensure_one()
        return {
            'employee_id': self.employee_id.id,
            'loan_id': self.id,
            'state': 'draft',
            'type_payment_order': 'loan',
            'company_id': self.company_id.id,
            'journal_id': self.journal_id.id,
            'amount_usd': self.loan_amount,
        }
        

    def action_create_payment_order(self):
        payment_order = self.env['hr.payment.order'].create(self.payment_vals())
        for rec in self:
            rec.payment_order_id = payment_order.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payment.order',
            'res_id': payment_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('installment_lines')
    def get_interest_count(self):
        for loan in self:
            count = 0
            if loan.installment_lines:
                count = len(loan.installment_lines)
            loan.installment_count = count

    # @api.depends('installment_lines','hr_payment_type')
    # def get_term_count(self):
    #     for loan in self:
    #         count = 0
    #         if loan.hr_payment_type == 'percentage':
    #             if loan.installment_lines:
    #                 count = len(loan.installment_lines)
    #             loan.term = count

    # @api.onchange('term','interest_rate','interest_type')
    # def onchange_term_interest_type(self):
    #     if self.loan_type_id:
    #         self.term = self.loan_type_id.loan_term
    #         self.interest_rate = self.loan_type_id.interest_rate
    #         self.interest_type = self.loan_type_id.interest_type
    
    # @api.onchange('hr_payment_type')
    # def onchange_hr_payment_type(self):
    #     if self.hr_payment_type == 'percentage':
    #         self.is_percentage = True
    #     else:
    #         self.is_percentage = False

    @api.depends('remaing_amount')
    def is_ready_to_close(self):
        for loan in self:
            ready = False
            if loan.remaing_amount <= 0 and loan.state == 'done':
                ready = True
            loan.is_close = ready

    @api.depends('installment_lines')
    def get_paid_amount(self):
        for loan in self:
            amt = 0
            for line in loan.installment_lines:
                if line.is_paid:
                    amt += line.amount
            loan.paid_amount = amt

    def compute_installment(self):
        vals = []
        date = self.start_date

        if self.employee_id.contract_id.state != 'open':
            raise UserError(f'El Empleado {self.employee_id.name} no tiene un contrato en ejecución')

        # if self.hr_payment_type == 'percentage':
        #     if self.period == 'bi-weekly':
        #         employee_salary = self.employee_id.contract_id.wage_usd
        #         percentage = 1
        #         salary = employee_salary / 2
        #         total_amount = self.loan_amount
        #         num_installments = self.term
        #         percentage = self.percentage
        #         max_deduction = salary * percentage
        #         num_installments = int(total_amount // max_deduction + (total_amount % max_deduction > 0))

        #         if date.day <= 15:
        #             date = date.replace(day=15)
        #         else:
        #             date = (date + relativedelta(months=1)).replace(day=1) + relativedelta(days=-1)

        #         for i in range(num_installments):
        #             if i > 0:
        #                 if date.day == 15:
        #                     date = (date + relativedelta(months=1)).replace(day=1) + relativedelta(days=-1)
        #                 else:
        #                     date = date.replace(day=15) + relativedelta(months=1)

        #             vals.append((0, 0, {
        #                 'name': f'Cuota - {self.name} - {i + 1}',
        #                 'employee_id': self.employee_id.id if self.employee_id else False,
        #                 'date': date,
        #                 # 'struct_id': self.struct_id.id,
        #                 'amount': max_deduction if i < num_installments - 1 else total_amount - sum(val[2]['amount'] for val in vals),
        #             }))

        if self.hr_payment_type == 'quota':
            # employee_complement = self.employee_id.contract_id.bono_ayuda_usd
            total_amount = self.loan_amount
            num_installments = self.term
            max_deduction = total_amount / num_installments
            # if max_deduction > employee_complement:
            #     raise UserError('El monto de las cuotas supera el monto del complemento.. debera asignar mas cuotas')
            
            if self.period == 'bi-weekly':
                if date.day <= 15:
                    date = date.replace(day=15)
                else:
                    date = (date + relativedelta(months=1)).replace(day=1) + relativedelta(days=-1)

                for i in range(num_installments):
                    if i > 0:
                        if date.day == 15:
                            date = (date + relativedelta(months=1)).replace(day=1) + relativedelta(days=-1)
                        else:
                            date = date.replace(day=15) + relativedelta(months=1)

                    vals.append((0, 0, {
                        'name': f'Cuota - {self.name} - {i + 1}',
                        'employee_id': self.employee_id.id if self.employee_id else False,
                        'date': date,
                        # 'struct_id': self.struct_id.id,
                        'amount': max_deduction,
                    }))
            elif self.period == 'monthly':
                if date.day <= 15:
                    date = date.replace(day=1) + relativedelta(months=1) + relativedelta(days=-1)
                else:
                    date = date.replace(day=1) + relativedelta(months=2) + relativedelta(days=-1)
                
                for i in range(num_installments):
                    vals.append((0, 0, {
                        'name': f'Cuota - {self.name} - {i + 1}',
                        'employee_id': self.employee_id.id if self.employee_id else False,
                        'date': date,
                        # 'struct_id': self.struct_id.id,
                        'amount': max_deduction,
                    }))
                    date = date.replace(day=1) + relativedelta(months=2) + relativedelta(days=-1)

        # elif self.hr_payment_type == 'indicador':
        #     total_amount = self.employee_id.contract_id.indicator_usd  # Monto del indicador (500)
        #     loan_amount = self.loan_amount  # Monto del préstamo (1500)
        #     percentage_to_deduct = self.percentage # Porcentaje a descontar (100% -> 1.0)
        #     amount_to_deduct = total_amount * percentage_to_deduct  # Monto a descontar por cuota
        #     remaining_amount = loan_amount  # Monto restante del préstamo
        #     date = self.start_date  # Fecha de inicio

        #     while remaining_amount > 0:
        #         if remaining_amount <= amount_to_deduct:
        #             deduction_amount = remaining_amount
        #         else:
        #             deduction_amount = amount_to_deduct

        #         vals.append((0, 0, {
        #             'name': f'Cuota - {self.name} - {len(vals) + 1}',
        #             'employee_id': self.employee_id.id if self.employee_id else False,
        #             'date': date,
        #             'struct_id': self.struct_id.id,
        #             'amount': deduction_amount,
        #         }))
                
        #         remaining_amount -= deduction_amount
        #         date = date + relativedelta(months=1)
        #         date = date.replace(day=1) + relativedelta(days=-1)

        #         if self.period == 'monthly':
        #             if date.day <= 15:
        #                 date = date.replace(day=1) + relativedelta(months=1) + relativedelta(days=-1)
        #             else:
        #                 date = date.replace(day=1) + relativedelta(months=2) + relativedelta(days=-1)

        if self.installment_lines:
            for l in self.installment_lines:
                l.unlink()
        self.installment_lines = vals

    @api.depends('paid_amount','loan_amount','interest_amount')
    def get_remaing_amount(self):
        for loan in self:
            remaining = (loan.loan_amount + loan.interest_amount) - loan.paid_amount
            loan.remaing_amount = remaining

    # @api.depends('loan_amount','interest_rate','is_apply_interest')
    # def get_interest_amount(self):
    #     for loan in self:
    #         amt = 0.0
    #         if loan.is_apply_interest:
    #             if loan.interest_rate and loan.loan_amount and loan.interest_type == 'liner':
    #                 loan.interest_amount = (loan.loan_amount * loan.term/12 * loan.interest_rate)/100
    #             if loan.interest_rate and loan.loan_amount and loan.interest_type == 'reduce':
    #                 loan.interest_amount = (loan.remaing_amount * loan.term/12 * loan.interest_rate)/100
    #                 for line in loan.installment_lines:
    #                     amt += line.ins_interest
    #         loan.interest_amount = amt



    # @api.depends('interest_amount')
    # def get_install_interest_amount(self):
    #     for loan in self:
    #         if loan.is_apply_interest:
    #             if loan.interest_amount and loan.term:
    #                 loan.ins_interest_amount = loan.interest_amount / loan.term

    # @api.onchange('interest_type','interest_rate')
    # def onchange_interest_rate_type(self):
    #     if self.interest_type and self.is_apply_interest:
    #         if self.interest_rate != self.loan_type_id.interest_rate:
    #             self.interest_rate = self.loan_type_id.interest_rate
    #         if self.interest_type != self.loan_type_id.interest_type:
    #             self.interest_type = self.loan_type_id.interest_type

    def get_loan_url(self):
        for loan in self:
            ir_param = self.env['ir.config_parameter'].sudo()
            base_url = ir_param.get_param('web.base.url')
            action_id = self.env.ref('l10n_ve_payroll.action_hr_employee_loan').id
            menu_id = self.env.ref('l10n_ve_payroll.menu_hr_employee_loan').id
            if base_url:
                base_url += '/web#id=%s&action=%s&model=%s&view_type=form&cids=&menu_id=%s' % (loan.id, action_id, 'hr.employee.loan', menu_id)
            loan.loan_url = base_url

    @api.depends('term','loan_amount')
    def get_installment_amount(self):
        amount = 0
        for loan in self:
            if loan.loan_amount and loan.term:
                amount = loan.loan_amount / loan.term
            loan.installment_amount = amount


    # @api.constrains('employee_id')
    # def _check_loan(self):
    #     now = datetime.now()
    #     year = now.year
    #     s_date = str(year)+'-01-01'
    #     e_date = str(year)+'-12-01'
        
    #     loan_ids = self.search([('employee_id','=',self.employee_id.id),('date','<=',e_date),('date','>=',s_date)])
    #     loan = len(loan_ids)
    #     if loan > self.employee_id.loan_request:
    #         raise ValidationError("Usted ya tiene %s préstamos en este año" % self.employee_id.loan_request)

    @api.constrains('loan_amount','term','loan_type_id','employee_id.loan_request')
    def _check_loan_amount_term(self):
        for loan in self:
            if loan.loan_amount <= 0:
                raise ValidationError("El monto del préstamo debe ser mayor que 0.00")

    # @api.onchange('loan_type_id')
    # def _onchange_loan_type(self):
    #     if self.loan_type_id:
    #         self.term = self.loan_type_id.loan_term
    #         self.is_apply_interest = self.loan_type_id.is_apply_interest
    #         if self.is_apply_interest:
    #             self.interest_rate = self.loan_type_id.interest_rate
    #             self.interest_type = self.loan_type_id.interest_type
        
    def action_send_request(self):
        amount_line = round(sum(self.installment_lines.mapped('amount')), 2)
        loan_amount = round(self.loan_amount, 2)

        if amount_line != loan_amount:
            raise ValidationError(_('La suma de los montos de las cuotas no puede ser mayor o menor al monto del prestamo'))

        if not self.manager_id:
            raise ValidationError(_('Por favor, seleccione el gerente de departamento !!!'))
        
        self.state = 'request'
        if not self.installment_lines:
            self.compute_installment()
        if self.manager_id and self.manager_id.work_email:
            ir_model_data = self.env['ir.model.data']
            try:
                template_id = ir_model_data._xmlid_lookup('l10n_ve_payroll.dev_dep_manager_request')
                # raise UserError(template_id)
                if template_id:
                    template_id = template_id[1]
                    mtp = self.env['mail.template']
                    template_id = mtp.browse(template_id)
                    template_id.write({'email_to': self.manager_id.work_email})
                    template_id.send_mail(self.ids[0], True)
                else:
                    raise ValidationError(_('No se encontró la plantilla de correo.'))
            except IndexError:
                raise ValidationError(_('Error al buscar la plantilla de correo. Verifique el XML ID.'))

    def get_hr_manager_email(self):
        group_id = self.env['ir.model.data']._xmlid_lookup('hr.group_hr_manager')[1]
        group_ids = self.env['res.groups'].browse(group_id)
        email=''
        if group_ids:
            employee_ids = self.env['hr.employee'].search([('user_id', 'in', group_ids.users.ids)])
            for emp in employee_ids:
                if email:
                    email = email+','+emp.work_email
                else:
                    email= emp.work_email
        return email

    def dep_manager_approval_loan(self):
        self.state = 'dep_approval'
        email = self.get_hr_manager_email()
        if email:
            ir_model_data = self.env['ir.model.data']
            template_id = ir_model_data._xmlid_lookup('l10n_ve_payroll.dev_hr_manager_request')[1]
            mtp = self.env['mail.template']
            template_id = mtp.browse(template_id)
            template_id.write({'email_to': email})
            template_id.send_mail(self.ids[0], True)

    def hr_manager_approval_loan(self):
        self.state = 'hr_approval'
        employee_id = self.env['hr.employee'].search([('user_id','=',self.env.user.id)],limit=1)
        self.hr_manager_id = employee_id and employee_id.id or False
        if self.employee_id.work_email and self.hr_manager_id:
            ir_model_data = self.env['ir.model.data']
            template_id = ir_model_data._xmlid_lookup('l10n_ve_payroll.hr_manager_confirm_loan')[1]
            mtp = self.env['mail.template']
            template_id = mtp.browse(template_id)
            template_id.write({'email_to': self.employee_id.work_email})
            template_id.send_mail(self.ids[0], True)

    def dep_manager_reject_loan(self):
        self.state = 'reject'
        if self.employee_id.work_email:
            ir_model_data = self.env['ir.model.data']
            template_id = ir_model_data._xmlid_lookup('l10n_ve_payroll.dep_manager_reject_loan')[1]
            mtp = self.env['mail.template']
            template_id = mtp.browse(template_id)
            template_id.write({'email_to': self.employee_id.work_email})
            template_id.send_mail(self.ids[0], True)

    def action_close_loan(self):
        self.state = 'close'
        if self.employee_id.work_email and self.hr_manager_id:
            ir_model_data = self.env['ir.model.data']
            template_id = ir_model_data._xmlid_lookup('l10n_ve_payroll.hr_manager_closed_loan')
            mtp = self.env['mail.template']
            template_id = mtp.browse(template_id[1])
            template_id.write({'email_to': self.employee_id.work_email})
            template_id.send_mail(self.ids[0], True)

    def hr_manager_reject_loan(self):
        self.state = 'reject'
        employee_id = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        self.hr_manager_id = employee_id and employee_id.id or False
        if self.employee_id.work_email and self.hr_manager_id:
            ir_model_data = self.env['ir.model.data']
            template_id = ir_model_data._xmlid_lookup('l10n_ve_payroll.hr_manager_reject_loan')
            mtp = self.env['mail.template']
            template_id = mtp.browse(template_id[1])
            template_id.write({'email_to': self.employee_id.work_email})
            template_id.send_mail(self.ids[0], True)

    def cancel_loan(self):
        self.state = 'cancel'

    def action_draft(self):
        self.state = 'draft'
        self.hr_manager_id = False
        
        if self.move_id:
            raise ValidationError(_('Debe pasar a borrador el asiento y eliminarlo'))

        if self.installment_lines:
            for l in self.installment_lines:
                l.unlink()

    def set_to_draft(self):
        self.state = 'draft'
        self.hr_manager_id = False

    def action_mark_paid(self):
        self.state = 'paid'

    def paid_loan(self):
        if not self.journal_id:
            raise ValidationError(_('Por favor, debe proporcionar el diario'))
        if not self.employee_id.address_id:
            raise ValidationError(_('Por favor, agregue la dirección del empleado !!!'))
        if self.payment_order_id.state not in ['approved','done']:
            raise ValidationError(_('No puede desembolzar mientras no se apruebe la Orden de Pago'))
            
        self.state = 'paid'
        trm = self.currency_id_dif.inverse_rate
        vals={
            'date': self.date,
            'ref': self.name,
            'tax_today': trm,
            'journal_id': self.journal_id and self.journal_id.id,
            'company_id': self.env.company.id,
        }
        acc_move_id = self.env['account.move'].create(vals)
        if acc_move_id:
            lst = []
            credit = self.loan_amount * trm
            bank = self.journal_id.default_account_id.id
            
            val = (0,0,{
                'account_id': bank,
                'partner_id': self.employee_id.address_id and self.employee_id.address_id.id or False,
                'name': self.name,
                'credit': credit or 0.0,
                'credit_usd': self.loan_amount or 0.0,
                'move_id': acc_move_id.id,
            })
            lst.append(val)

            debit_amount = credit
            val = (0,0,{
                'account_id': self.loan_account.id,
                'partner_id':self.employee_id.address_id and self.employee_id.address_id.id or False,
                'name':self.name,
                'debit':debit_amount or 0.0,
                'debit_usd': self.loan_amount or 0.0,
                'move_id': acc_move_id.id,
            })
            lst.append(val)
            acc_move_id.line_ids = lst
            acc_move_id.action_post()
            self.move_id = acc_move_id.id

    def view_journal_entry(self):
        if self.move_id:
            return {
                'view_mode': 'form',
                'res_id': self.move_id.id,
                'res_model': 'account.move',
                'view_type': 'form',
                'type': 'ir.actions.act_window',
            }            
            
    def action_done_loan(self):
        can = any(self.installment_lines.filtered(lambda line: not line.is_paid and not line.is_skip))
        if can:
            raise UserError('No puede cerrar el prestamo ya que existen cuotas sin cancelar')
        self.state = 'done'

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('hr.employee.loan') or '/'
        return super(HREmployeeLoan, self).create(vals)
        
    def copy(self, default=None):
        if default is None:
            default = {}
        default['name'] = '/'
        return super(HREmployeeLoan, self).copy(default=default)
    
    def unlink(self):
        for loan in self:
            if loan.state != 'draft':
                raise ValidationError(_('Loan delete in draft state only !!!'))
        return super(HREmployeeLoan,self).unlink()

    def action_view_loan_installment(self):
        action = self.env.ref('l10n_ve_payroll.action_installment_line').read()[0]

        installment = self.mapped('installment_lines')
        if len(installment) > 1:
            action['domain'] = [('id', 'in', installment.ids)]
        elif installment:
            action['views'] = [(self.env.ref('l10n_ve_payroll.view_loan_emi_form').id, 'form')]
            action['res_id'] = installment.id
        return action

    # @api.constrains('installment_lines')
    # def validate_amount(self):
    #     for rec in self:
    #         if len(rec.installment_lines) > 0:
    #             amount_lines = sum(rec.installment_lines.mapped('amount'))
    #             if amount_lines > 0:
    #                 if amount_lines > rec.loan_amount or amount_lines < rec.loan_amount:
    #                     raise ValidationError(_("Por favor asegúrese que el monto total de las cuotas no sea mayor o menor que el monto del préstamo"))
