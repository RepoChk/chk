# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import formatLang

class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    struct_id = fields.Many2one(
        'hr.payroll.structure',
        related='slip_ids.struct_id',
        store=True,
    )

    payslip_exceeded_count = fields.Integer(compute='_compute_payslip_exceeded_count')

    def _compute_payslip_exceeded_count(self):
        for payslip_run in self:
            payslip_run.payslip_exceeded_count = len(payslip_run.slip_ids.filtered(lambda l: l.discount_status == 'excedido'))

    def action_open_payslips_exceeded(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.payslip",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [['id', 'in', self.slip_ids.filtered(lambda l: l.discount_status == 'excedido').ids]],
            "context": {'default_payslip_run_id': self.id},
            "name": "Recibos Excedidos",
        }

    def action_validate(self):
        if self.payslip_exceeded_count >= 1:
            raise UserError("Hay recibos que exceden los descuentos permitidos.")
        return super(HrPayslipRun, self).action_validate()