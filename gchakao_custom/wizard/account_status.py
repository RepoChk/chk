from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime, timedelta

class AccountStatusWizard(models.TransientModel):
    _name = 'account.status.wizard'
    _description = 'Asistente para imprimir Estado de cuentas de un Cliente'

    partner_ids = fields.Many2many('res.partner', string="Clientes")
    invoice_user_ids = fields.Many2many('res.users', string="Vendedores de la Factura", 
        default=lambda self: self.env.user, readonly=True
        )
    company_ids = fields.Many2many('res.company', string="Compañías")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    invoice_ids = fields.Many2many('account.move', string="Facturas", compute='_compute_invoices')
    start_date = fields.Date(string='Fecha Inicio (Facturación)', default=lambda self: datetime(self.env.context.get('current_year', datetime.now().year), 1, 1))
    ending_date = fields.Date(string='Fecha Fin (Facturación)', default=lambda self: datetime.now().date())

    @api.model
    def default_get(self, fields):
        res = super(AccountStatusWizard, self).default_get(fields)
        user = self.env.user
        sales_force_group = self.env.ref('gchakao_custom.group_sales_force_user')
        sales_force_manager_group = self.env.ref('gchakao_custom.group_sales_force_manager')

        if sales_force_group in user.groups_id:
            if sales_force_manager_group in user.groups_id:
                users_under_manager = self.env['res.users'].search([
                    ('partner_id.team_id.id', '=', user.partner_id.team_id.id)
                ])
                res['invoice_user_ids'] = [(4, u.id) for u in users_under_manager]
            else:
                res['invoice_user_ids'] = [(4, user.id)]
        
        return res

    @api.onchange('invoice_user_ids')
    def _onchange_invoice_user_ids(self):
        user = self.env.user
        sales_force_group = self.env.ref('gchakao_custom.group_sales_force_user')
        sales_force_manager_group = self.env.ref('gchakao_custom.group_sales_force_manager')

        if sales_force_group in user.groups_id:
            if sales_force_manager_group not in user.groups_id:
                allowed_users = [user.id]
                selected_users = self.invoice_user_ids.ids
                
                if any(u not in allowed_users for u in selected_users):
                    self.invoice_user_ids = [(6, 0, allowed_users)]
                    return {'warning': {'title': "Acción no permitida", 'message': "Tú perfil como Asesor de Ventas no te permite ejecutar esta acción. No tiene permiso para añadir otros usuarios a la lista de Vendedores."}}
            else:
                default_users = self.env['res.users'].search([
                    ('partner_id.team_id.id', '=', user.partner_id.team_id.id)
                ]).ids
                selected_users = self.invoice_user_ids.ids
                
                if any(u not in default_users for u in selected_users):
                    self.invoice_user_ids = [(6, 0, default_users)]
                    return {'warning': {'title': "Selección restringida", 'message': "Tú perfil como Gerente de Ventas no te permite ejecutar esta acción. No tiene permiso para añadir otros usuarios a la lista de Vendedores predeterminada de tu Gerencia."}}

    @api.depends('partner_ids', 'invoice_user_ids', 'company_ids', 'start_date', 'ending_date')
    def _compute_invoices(self):
        for record in self:
            # Consulta SQL
            query = """
                SELECT id 
                FROM account_move
                WHERE move_type = 'out_invoice'
                AND state = 'posted'
                AND date >= %s
                AND date <= %s
            """
            params = [record.start_date, record.ending_date]
            
            if record.partner_ids:
                partner_ids = tuple(record.partner_ids.ids)
                query += " AND partner_id IN %s"
                params.append(partner_ids)
                
            if record.invoice_user_ids:
                user_ids = tuple(record.invoice_user_ids.ids)
                query += " AND invoice_user_id IN %s"
                params.append(user_ids)
                
            if record.company_ids:
                company_ids = tuple(record.company_ids.ids)
                query += " AND company_id IN %s"
                params.append(company_ids)
                
            # Ejecutar la consulta con sudo()
            self.env.cr.execute(query, params)
            invoice_ids = [row[0] for row in self.env.cr.fetchall()]
            
            # Obtener los registros con sudo()
            record.invoice_ids = self.env['account.move'].sudo().browse(invoice_ids)

    def _calculate_credit_and_overdue_days(self, invoice):
        credit_days = (invoice.invoice_date_due - invoice.invoice_date).days if invoice.invoice_date_due and invoice.invoice_date else 0
        overdue_days = (fields.Date.today() - invoice.invoice_date_due).days if invoice.invoice_date_due else 0
        return credit_days, overdue_days

    def _get_invoice_payments(self, invoice):
        # Usar sudo() para evitar problemas de permisos
        self = self.sudo()
        # Consulta SQL directa para obtener los pagos
        query = """
            SELECT 
                c.name AS name,
                TO_CHAR(c.date, 'DD/MM/YYYY') AS date,
                aj.name ->> 'es_VE'::text AS journal_id,
                rc.name AS currency_id,
                c.ref AS ref,
                COALESCE(c.tax_today, 0.0) AS tax_today,
                COALESCE(SUM(apr.amount_usd), 0.0) AS amount,
                COALESCE(SUM(apr.amount_usd), 0.0) AS total_payment
            FROM account_payment ap
            LEFT JOIN account_move c ON ap.move_id = c.id
            LEFT JOIN account_journal aj ON c.journal_id = aj.id
            LEFT JOIN res_currency rc ON ap.currency_id = rc.id
            LEFT JOIN account_move_line aml_payment ON aml_payment.payment_id = ap.id
            LEFT JOIN account_partial_reconcile apr ON (
                apr.credit_move_id = aml_payment.id OR 
                apr.debit_move_id = aml_payment.id
            )
            LEFT JOIN account_move_line aml_invoice ON (
                (apr.debit_move_id = aml_invoice.id AND aml_invoice.move_id = %s) OR
                (apr.credit_move_id = aml_invoice.id AND aml_invoice.move_id = %s)
            )
            WHERE c.state = 'posted'
            AND (aml_invoice.move_id = %s OR ap.move_id IN (
                SELECT move_id 
                FROM account_move_line 
                WHERE move_id = %s
            ))
            GROUP BY c.name, c.date, aj.name, rc.name, c.ref, c.tax_today
        """
        self.env.cr.execute(query, [invoice.id, invoice.id, invoice.id, invoice.id])
        payments = self.env.cr.dictfetchall()
        
        # Calcular el total de pagos
        total_payments = sum(payment.get('amount', 0.0) for payment in payments)
        
        return payments

    def _get_applied_amount(self, payment, invoice):
        applied_amount = 0.0

        # Buscar todas las reconciliaciones parciales asociadas al pago
        reconciliations = self.env['account.partial.reconcile'].search([('credit_move_id.payment_id', '=', payment.id)])

        for rec in reconciliations:
            # Verificar que la reconciliación se refiere a la factura correcta
            if rec.debit_move_id.move_id == invoice:
                applied_amount += rec.amount_usd or 0  # Asegurarse de que no se sumen valores nulos

        return applied_amount

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

    def _get_credit_notes_for_invoice(self, invoice):
        # Consulta SQL directa para obtener las notas de crédito
        query = """
            SELECT 
                am.invoice_number AS credit_note_number,
                TO_CHAR(am.invoice_date, 'DD/MM/YYYY') AS credit_note_date,
                am.motive AS credit_note_motive,
                am.amount_total_usd AS credit_note_amount,
                SUM(am.amount_total_usd) OVER () AS total_credit_notes
            FROM account_move am
            WHERE am.reversed_entry_id = %s
            AND am.move_type = 'out_refund'
            AND am.state = 'posted'
        """
        self.env.cr.execute(query, [invoice.id])
        credit_notes = self.env.cr.dictfetchall()
        
        # Calcular el total de notas de crédito
        total_credit_notes = sum(note.get('credit_note_amount', 0.0) for note in credit_notes)
        
        # Agregar el total a cada nota de crédito
        for note in credit_notes:
            note['total_credit_notes'] = total_credit_notes
            
        return credit_notes
    
    def _get_withholdings(self, invoice):
        withholdings = []
        
        # Retención de IVA (solo si está aplicada)
        if invoice.wh_iva_id and invoice.wh_iva_id.state == 'done':
            amount = invoice.wh_iva_id.total_tax_ret / invoice.tax_today if invoice.tax_today else invoice.wh_iva_id.total_tax_ret
            withholdings.append({
                'type': 'IVA',
                'number': invoice.wh_iva_id.number,
                'date': invoice.wh_iva_id.date_ret,
                'amount': amount,
                'currency': invoice.wh_iva_id.currency_id.name,
                'description': 'Retención de IVA'
            })
        
        # Retención de ISLR (solo si está aplicada)
        if invoice.islr_wh_doc_id and invoice.islr_wh_doc_id.state == 'done':
            amount = invoice.islr_wh_doc_id.amount_total_ret / invoice.tax_today if invoice.tax_today else invoice.islr_wh_doc_id.amount_total_ret
            withholdings.append({
                'type': 'ISLR',
                'number': invoice.islr_wh_doc_id.number,
                'date': invoice.islr_wh_doc_id.date_ret,
                'amount': amount,
                'currency': invoice.islr_wh_doc_id.currency_id.name,
                'description': 'Retención de ISLR'
            })
        
        return withholdings
    
    def _prepare_data(self):
        self.ensure_one()
        if not self.invoice_ids:
            raise UserError("No se encontraron facturas para los filtros seleccionados.")
        
        # Usar sudo() para evitar problemas de permisos
        self = self.sudo()
        # Consulta SQL directa para obtener los datos principales
        query = """
            SELECT 
                am.id AS invoice_id,
                rp.id AS partner_id,
                rp.name AS partner_name,
                rp.customer_type,
                rp.customer_segmentation,
                rc.name AS company_name,
                x.name AS invoice_user_name,
                am.invoice_number,
                TO_CHAR(am.invoice_date, 'DD/MM/YYYY') AS invoice_date,
                TO_CHAR(am.delivery_date, 'DD/MM/YYYY') AS delivery_date,
                TO_CHAR(am.invoice_date_due, 'DD/MM/YYYY') AS invoice_date_due,
                apt.name AS payment_term,
                (am.invoice_date_due - am.invoice_date) AS credit_days,
                (CURRENT_DATE - am.invoice_date_due) AS overdue_days,
                am.tax_today AS tax_today,
                COALESCE(am.amount_total_usd, 0.0) AS amount_total_usd,
                COALESCE(am.amount_residual_usd, 0.0) AS amount_residual_usd
            FROM account_move am
            JOIN res_partner rp ON am.partner_id = rp.id
            JOIN res_company rc ON am.company_id = rc.id
            JOIN res_users ru ON am.invoice_user_id = ru.id
            LEFT JOIN res_partner x ON x.id = ru.partner_id
            LEFT JOIN account_payment_term apt ON am.invoice_payment_term_id = apt.id
            WHERE am.id IN %s
        """
        self.env.cr.execute(query, [tuple(self.invoice_ids.ids)])
        results = self.env.cr.dictfetchall()

        # Procesar los resultados
        data = []
        for row in results:
            invoice = self.env['account.move'].browse(row['invoice_id'])
            payments = self._get_invoice_payments(invoice)
            credit_notes = self._get_credit_notes_for_invoice(invoice)
            invoice_lines = self._get_invoice_lines(invoice)
            withholdings = self._get_withholdings(invoice)  # Nuevo: Obtener retenciones

            # Calcular los totales
            total_payments = sum(payment.get('amount', 0.0) for payment in payments)
            total_withholdings = sum(w['amount'] for w in withholdings)
            total_credit_notes = sum(credit_note.get('credit_note_amount', 0.0) for credit_note in credit_notes)
            total_credit = total_credit_notes + total_withholdings  # Nuevo: Total de crédito (NC + retenciones)

            # Calcular el balance
            balance = row['amount_residual_usd']

            result = {
                'partner_id': row['partner_id'],
                'partner_name': row['partner_name'],
                'customer_type': row['customer_type'],
                'customer_segmentation': row['customer_segmentation'],
                'company_id': row['company_name'],
                'invoice_user_id': row['invoice_user_name'],
                'invoice': row['invoice_number'],
                'invoice_date': row['invoice_date'],
                'delivery_date': row['delivery_date'],
                'invoice_date_due': row['invoice_date_due'],
                'invoice_payment_term_id': row['payment_term'],
                'credit_days': row['credit_days'] if row['credit_days'] else 0,
                'overdue_days': row['overdue_days'] if row['overdue_days'] else 0,
                'tax_today': row['tax_today'],
                'amount': row['amount_total_usd'],
                'payment': total_payments,
                'credit_note': total_credit_notes,
                'withholdings': withholdings,
                'total_withholdings': total_withholdings,
                'total_credit': total_credit,  # Nuevo: Total de crédito
                'balance': balance,  # Balance ajustado
                'status': 'R' if total_credit_notes >= row['amount_total_usd']
                            else 'P' if balance <= 0
                            else 'V' if row['overdue_days'] > 0
                            else 'XV',
                'payments': payments,
                'has_payments': bool(payments),
                'credit_notes': credit_notes,
                'invoice_lines': invoice_lines
            }
            data.append(result)

        # Ordenar los datos por nombre de compañía y fecha de vencimiento
        data.sort(key=lambda x: (x['company_id'], x['invoice_date_due']))

        # Preparar los datos finales para el reporte
        datas = {
            'data': data,
            '_name': 'Estado de Cuenta',
            'company_id': self.company_id.id,
            'customer': ', '.join(self.partner_ids.mapped('name')) if self.partner_ids else 'Todos los Clientes',
            'total': sum(row.get('amount_total_usd', 0.0) for row in data)
        }
        
        return datas

    def print_account_status(self):
        self.ensure_one()
        user = self.env.user
        sales_force_group = self.env.ref('gchakao_custom.group_sales_force_user')
        sales_force_manager_group = self.env.ref('gchakao_custom.group_sales_force_manager')

        # Validación de campo obligatorio para grupos de ventas
        if sales_force_group in user.groups_id and not self.invoice_user_ids:
            raise UserError("El campo Vendedores es obligatorio para Vendedores y Gerentes de Ventas")

        data = self._prepare_data()
        return self.env.ref('gchakao_custom.action_report_account_status').report_action([], data=data)

    def print_account_status_detailed(self):
        self.ensure_one()
        user = self.env.user
        sales_force_group = self.env.ref('gchakao_custom.group_sales_force_user')
        
        # Nueva validación para campo obligatorio
        if sales_force_group in user.groups_id:
            if not self.invoice_user_ids:
                raise UserError("El campo Vendedores es obligatorio para Vendedores y Gerentes de Ventas")
        
        data = self._prepare_data()
        if not data:
            raise UserError("No se generaron datos para el reporte.")
        return self.env.ref('gchakao_custom.action_report_account_status_detailed').report_action([], data=data)
