# -*- coding: utf-8 -*-

from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    installment_ids = fields.Many2many('hr.employee.loan.installment.line', string='Cuotas de Préstamos', domain="[('employee_id','=', employee_id), ('is_paid', '=', False), ('is_skip', '=', False)]")

    @api.depends('installment_ids')
    def get_installment_amount(self):
        for payslip in self:
            amount = 0
            int_amount = 0
            if payslip.installment_ids:
                for installment in payslip.installment_ids:
                    if not installment.is_skip:
                        amount += installment.amount * payslip.tasa_cambio
                    int_amount += installment.ins_interest

            payslip.installment_amount = amount
            payslip.installment_int = int_amount

    # PARA QUE SE EJECUTE DEBO COMENTAR LA FUNCION DEL ADDON DE JOSE LUIS grupochakao/l10n_ve_payroll/models/hr_payslip.py
    def compute_sheet(self):
        for rec in self:
            rec._calcular_lunes()
            installment_ids = self.env['hr.employee.loan.installment.line'].search(
                [('employee_id', '=', rec.employee_id.id), ('loan_id.state', '=', 'paid'), ('is_skip', '=', False),
                 ('is_paid', '=', False), ('date', '<=', rec.date_to), ('struct_id', '=', rec.struct_id.id)])
            
            if installment_ids:
                rec.installment_ids = [(6, 0, installment_ids.ids)]
            else:
                rec.installment_ids = [(5, 0, 0)]
            
            if len(self.worked_days_line_ids) > 0:
                self._actualizar_tabla()
        
        res = super(HrPayslip, self).compute_sheet()
        return res

    @api.onchange('employee_id')
    def onchange_employee(self):
        if self.employee_id:
            installment_ids = self.env['hr.employee.loan.installment.line'].search(
                [('employee_id', '=', self.employee_id.id), ('loan_id.state', '=', 'paid'),
                 ('is_paid', '=', False), ('date', '<=', self.date_to), ('struct_id', '=', self.struct_id.id)])
            if installment_ids:
                self.installment_ids = [(6, 0, installment_ids.ids)]
            else:
                self.installment_ids = [(5, 0, 0)]


    @api.onchange('installment_ids')
    def onchange_installment_ids(self):
        # if self.employee_id:
        #     installment_ids = self.env['hr.employee.loan.installment.line'].search(
        #         [('employee_id', '=', self.employee_id.id), ('loan_id.state', '=', 'paid'),
        #          ('is_paid', '=', False), ('date', '<=', self.date_to), ('struct_id', '=', self.struct_id.id)])
        #     if installment_ids:
        #         self.installment_ids = [(6, 0, installment_ids.ids)]
        #     else:
        #         self.installment_ids = [(5, 0, 0)]
        return False

    def action_payslip_cancel(self):
        res =  super().action_payslip_cancel()
        for rec in self:
            loan_lines = self.env['hr.employee.loan.installment.line'].search([('payslip_id', '=', rec.id)])
            if loan_lines:
                loan = loan_lines.mapped('loan_id')
                if loan.state == 'close':
                    raise UserError(f'Este recibo de nómina esta asociado a un Préstamo [{loan.name}] en estatus "CERRADO".')
                for line in loan_lines:
                    line.is_paid = False
                    line.payslip_id = False
        return res






