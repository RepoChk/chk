from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime, timedelta

class AccountReceivableSupplierWizard(models.TransientModel):
    _name = 'account.receivable.supplier.wizard'
    _description = 'Asistente para imprimir Cuentas por Pagar de un proveedor'

    partner_ids = fields.Many2many('res.partner', string="Proveedores")
    company_ids = fields.Many2many('res.company', string="Compañías")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    invoice_ids = fields.Many2many('account.move', string="Facturas", compute='_compute_invoices')

    @api.depends('partner_ids', 'company_ids')
    def _compute_invoices(self):
        for record in self:
            domain = [
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted'),
                ('amount_residual_usd', '>', 0)
            ]
            if record.partner_ids:
                domain.append(('partner_id', 'in', record.partner_ids.ids))
            if record.company_ids:
                domain.append(('company_id', 'in', record.company_ids.ids))
            record.invoice_ids = self.env['account.move'].search(domain)

    def _calculate_credit_and_overdue_days(self, invoice):
        credit_days = (invoice.invoice_date_due - invoice.invoice_date).days if invoice.invoice_date_due and invoice.invoice_date else 0
        overdue_days = (fields.Date.today() - invoice.invoice_date_due).days if invoice.invoice_date_due else 0
        return credit_days, overdue_days

    def _prepare_data(self):
        self.ensure_one()
        if not self.invoice_ids:
            raise UserError("No se encontraron facturas para los filtros seleccionados.")
        
        data = []
        for inv in self.invoice_ids:
            credit_days, overdue_days = self._calculate_credit_and_overdue_days(inv)
            result = {
                'partner_id': inv.partner_id.id,
                'partner_name': inv.partner_id.name,
                'company_id': inv.company_id.name,
                'invoice': inv.supplier_invoice_number,
                'invoice_date': inv.invoice_date,
                'delivery_date': inv.delivery_date,
                'invoice_date_due': inv.invoice_date_due,
                'invoice_payment_term_id': inv.invoice_payment_term_id.name,
                'credit_days': credit_days,
                'overdue_days': overdue_days,
                'tax_rate': inv.tax_today,
                'amount': inv.amount_total_usd,
                'payment': inv.amount_total_usd - inv.amount_residual_usd,
                'credit_note': sum(inv.reversed_entry_id.mapped('amount_total_usd')) if inv.reversed_entry_id else 0,
                'balance': inv.amount_residual_usd,
                'status': 'V' if overdue_days > 0 else 'XV',
            }
            data.append(result)

        return {
            'data': data,
            '_name': 'Cuentas por Pagar de un proveedor',
            'company_id': self.company_id.id,
            'customer': ', '.join(self.partner_ids.mapped('name')) if self.partner_ids else 'Todos los Proveedores',
            'total': sum(inv.amount_total_usd for inv in self.invoice_ids)
        }

    def print_account_receivable_supplier(self):
        data = self._prepare_data()
        if not data:
            raise UserError("No se generaron datos para el reporte.")
        return self.env.ref('gchakao_custom.action_report_account_receivable_supplier').report_action(self, data={'doc': data})