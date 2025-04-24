from odoo import api, fields, models, http, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime, timedelta

class CommissionUpdateWizard(models.TransientModel):
    _name = 'commission.update.wizard'
    _description = 'Actualización de comisiones'

    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)

    def _get_default_contract_ids(self):
        struct = self.env.context.get('structure_id')
        journal = self.env.context.get('journal_id')
        struct_id = self.env['hr.payroll.structure'].sudo().browse(struct)
        company_id = self.env['account.journal'].sudo().browse(journal).company_id
        contract_ids = []
        for employee in struct_id.employee_ids.filtered(lambda l: l.company_id == company_id):
            contract_ids.append(employee.employee_id.with_context(struct=struct).contract_id.id)
        return [(6, 0, contract_ids)]

    contract_ids = fields.Many2many(
        'hr.contract',
        string='Contratos',
        required=True,
        default=_get_default_contract_ids,
    )

    def action_update(self):
        if not self.contract_ids:
            raise UserError("No hay contratos para actualizar")
        for line in self.contract_ids:
            line.sudo().write({
                'commission_usd' : line.commission_usd,
                'commission_bs' : line.commission_bs,
            })
        return True