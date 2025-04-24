# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta


class HRLoanInstallmentLine(models.Model):
    _name = 'hr.employee.loan.installment.line'
    _description = 'Lineas de Cuotas'
    _order = 'date,name'
    
    name = fields.Char('Nombre')
    employee_id = fields.Many2one('hr.employee',string='Empleado',required=True)
    loan_id = fields.Many2one('hr.employee.loan',string='Préstamo',required=True, ondelete='cascade')
    date = fields.Date('Fecha')
    is_paid = fields.Boolean('Pagado')
    amount = fields.Monetary('Monto', currency_field='currency_id_dif')
    interest = fields.Monetary('Total Intereses', currency_field='currency_id_dif')
    ins_interest = fields.Monetary('Interés', currency_field='currency_id_dif')
    installment_amt = fields.Monetary('Cuota Capital', currency_field='currency_id_dif')
    total_installment = fields.Monetary('Total Cuota', compute='get_total_installment', currency_field='currency_id_dif')
    payslip_id = fields.Many2one('hr.payslip', string='Nómina')
    is_skip = fields.Boolean('Saltar')
    move_id = fields.Many2one('account.move', string='Asiento Contable')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id_dif = fields.Many2one('res.currency', string='Moneda', related='company_id.currency_id_dif', readonly=True)

    struct_id = fields.Many2one('hr.payroll.structure', string='Descontar en',)
    
    @api.depends('installment_amt','ins_interest')
    def get_total_installment(self):
        for line in self:
            line.total_installment = line.ins_interest + line.installment_amt
        
    def action_view_payslip(self):
        if self.payslip_id:
            return {
                'view_mode': 'form',
                'res_id': self.payslip_id.id,
                'res_model': 'hr.payslip',
                'view_type': 'form',
                'type': 'ir.actions.act_window',
                
            }

    def action_view_move(self):
        if self.move_id:
            return {
                'view_mode': 'form',
                'res_id': self.move_id.id,
                'res_model': 'account.move',
                'view_type': 'form',
                'type': 'ir.actions.act_window',
                
            }

    def action_pay_wizard(self):
        # self.loan_id.validate_amount()
        return {
            'name': _('Pago de Cuota'),
            'type': 'ir.actions.act_window',
            'res_model': 'pay.fee',
            'view_mode': 'form',
            'context': {
                'default_amount': self.amount,
                'default_line_id': self.id,
            },
            'target': 'new',
        }

    def action_cancel_move(self):
        for rec in self:
            if rec.move_id:
                rec.move_id.button_cancel()
                rec.write({'move_id': False, 'is_paid': False})
                user = self.env.user
                date = datetime.now()
                new_date = date - timedelta(hours=4)
                formatted_date = new_date.strftime('%d-%m-%Y %H:%M')
                message = _(
                    'El usuario %(user_name)s cancelo el asiento contable de la cuota %(name)s el %(date)s.',
                    user_name=user.name,
                    name=rec.name,
                    date=formatted_date
                )
                rec.loan_id.message_post(body=message)

    @api.model
    def unlink(self):
        for line in self:
            if line.loan_id.state in ['done','close']:
                raise UserError("No se pueden eliminar las líneas de cuotas de un préstamo en el estado actual.")
        return super(HRLoanInstallmentLine, self).unlink()
