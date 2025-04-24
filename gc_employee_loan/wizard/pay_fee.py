# -*- coding: utf-8 -*-

from odoo import models, _, fields, api
from odoo.exceptions import UserError


class PayFee(models.TransientModel):
    _name = 'pay.fee'
    _description = 'Pagar cuota'

    name = fields.Char('Nombre', related='loan_line_id.name')
    loan_line_id = fields.Many2one('hr.employee.loan.installment.line', string='Cuota', required=True, default=lambda self: self.env.context.get('default_line_id'))
    employee_id = fields.Many2one('hr.employee', related='loan_line_id.employee_id', string='Empleado', required=True)
    date = fields.Date('Fecha', default=fields.Date.today)
    amount = fields.Monetary('Monto', currency_field='currency_id_dif', default=lambda self: self.env.context.get('default_amount'))
    total_installment = fields.Monetary('Total Préstamo', compute='_compute_total', currency_field='currency_id_dif')
    total_debt = fields.Monetary('Total Deuda', compute='_compute_total', currency_field='currency_id_dif')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id_dif = fields.Many2one('res.currency', string='Moneda', related='company_id.currency_id_dif',)

    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        required=True,
        check_company=True,
    )

    @api.depends('loan_line_id')
    def _compute_total(self):
        total_installment = self.loan_line_id.loan_id.loan_amount
        paid = sum(self.loan_line_id.loan_id.installment_lines.filtered(lambda line: line.is_paid).mapped('amount'))
        self.total_debt = total_installment - paid
        self.total_installment = total_installment

    def action_pay_line(self):
        if not self.employee_id.address_id:
            raise ValidationError(_('Por favor, agregue la dirección del empleado !!!'))
        if self.loan_line_id.is_skip:
            raise ValidationError(_('Por favor, si desea pagar debe desmarcar la casilla de "Saltar"'))

        vals = {
            'date': self.date,
            'ref': f'Abono a préstamo: {self.name}',
            'journal_id': self.journal_id.id,
            'company_id': self.env.company.id
        }
        acc_move_id = self.env['account.move'].create(vals)

        if acc_move_id:
            lst = []
            trm = self.currency_id_dif.inverse_rate
            debit = self.amount * trm
            
            val = (0, 0, {
                'account_id': self.journal_id.default_account_id.id,
                'partner_id': self.employee_id.address_id.id,
                'name': f'Abono: {self.name}',
                'debit': debit or 0.0,
                'debit_usd': self.amount or 0.0,
                'move_id': acc_move_id.id,
            })
            lst.append(val)

            val = (0, 0, {
                'account_id': self.loan_line_id.loan_id.loan_account.id,
                'partner_id': self.employee_id.address_id.id,
                'name': f'Abono: {self.name}',
                'credit': debit or 0.0,
                'credit_usd': self.amount or 0.0,
                'move_id': acc_move_id.id,
            })
            lst.append(val)

            acc_move_id.line_ids = lst
            acc_move_id.action_post()

            line = self.env['hr.employee.loan.installment.line'].browse(self.loan_line_id.id)
            line.is_paid = True
            line.amount = self.amount
            line.move_id = acc_move_id.id