# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class HrPaymentOrder(models.Model):
    _inherit = 'hr.payment.order'

    loan_id = fields.Many2one('hr.employee.loan', string='Préstamos de empleado',)

    def action_confirm(self):
        res = super(HrPaymentOrder, self).action_confirm()
        for rec in self:
            if rec.loan_id:
                rec.loan_id.payment_order_id = rec.id
        return res

    # def action_send_approval(self):
    #     res = super(HrPaymentOrder, self).action_send_approval()
    #     for rec in self:
    #         rec.loan_id.journal_id = rec.journal_id.id
    #     return res

    def action_create_payment(self):
        res = super(HrPaymentOrder, self).action_create_payment()
        for rec in self:
            if rec.loan_id:
                rec.loan_id.journal_id = rec.journal_id.id
        return res