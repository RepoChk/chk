from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime, timedelta

class AccountStatusSupplierWizard(models.TransientModel):
    _name = 'account.status.supplier.wizard'
    _description = 'Asistente para imprimir Estado de cuentas de un Proveedor'

    partner_ids = fields.Many2many('res.partner', string="Proveedores")
    company_ids = fields.Many2many('res.company', string="Compañías")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    invoice_ids = fields.Many2many('account.move', string="Facturas", compute='_compute_invoices')
    start_date = fields.Date(string='Fecha Inicio (Facturación)', default=lambda self: datetime(self.env.context.get('current_year', datetime.now().year), 1, 1))
    ending_date = fields.Date(string='Fecha Fin (Facturación)', default=lambda self: datetime.now().date())
    
    @api.depends('partner_ids','company_ids', 'start_date', 'ending_date')
    def _compute_invoices(self):
        for record in self:
            domain = [
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted'),
                ('date', '>=', record.start_date),
                ('date', '<=', record.ending_date)
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

    def _get_invoice_payments(self, invoice):
        payments = invoice.sudo().invoice_payments_widget and invoice.sudo().invoice_payments_widget['content'] or []
        payment_data = []
        for p in payments:
            payment = self.env['account.payment'].browse(int(p['account_payment_id']))
            if payment.state == 'posted' and payment.name:
                payment_data.append({
                    'name': payment.name,
                    'date': payment.date,
                    'journal_id': payment.journal_id.name,
                    'currency_id': payment.currency_id.name,
                    'ref': payment.ref,
                    'tax_today': payment.tax_today,
                    'amount': payment.amount_ref,
                })
        return payment_data

    def _get_invoice_lines(self, invoice):
        lines = []
        for line in invoice.invoice_line_ids:
            lines.append({
                'product_code': line.product_id.default_code,
                'product_id': line.product_id.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'discount': line.discount,
                'price_subtotal_usd': line.price_subtotal_usd,
                'price_subtotal': line.price_subtotal,
                'tax_ids': [(tax.name, tax.amount) for tax in line.tax_ids],
            })
        return lines

    def _prepare_data(self):
        self.ensure_one()
        if not self.invoice_ids:
            raise UserError("No se encontraron facturas para los filtros seleccionados.")
        
        data = []
        for inv in self.invoice_ids:
            credit_days, overdue_days = self._calculate_credit_and_overdue_days(inv)
            payments = self._get_invoice_payments(inv)
            invoice_lines = self._get_invoice_lines(inv)  # Fetch invoice lines here
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
                'status': 'P' if inv.amount_residual_usd == 0 else 'V' if overdue_days > 0 else 'XV',
                'payments': payments,
                'has_payments': bool(payments),
                'invoice_lines': invoice_lines,
            }
            data.append(result)
        return {
            'data': data,
            '_name': 'Estado de Cuenta',
            'company_id': self.company_id.id,
            'customer': ', '.join(self.partner_ids.mapped('name')) if self.partner_ids else 'Todos los Clientes',
            'total': sum(inv.amount_total_usd for inv in self.invoice_ids)
        }


    def print_account_status_supplier(self):
        data = self._prepare_data()
        if not data:
            raise UserError("No se generaron datos para el reporte.")
        return self.env.ref('gchakao_custom.action_report_account_status_supplier').report_action(self, data={'doc': data})

    def print_account_status_supplier_detailed(self):
        data = self._prepare_data()
        if not data:
            raise UserError("No se generaron datos para el reporte.")
        return self.env.ref('gchakao_custom.action_report_account_status_supplier_detailed').report_action(self, data={'doc': data})