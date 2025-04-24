from odoo import models, fields, api
from datetime import datetime, timedelta  # Asegúrate de importar timedelta
from odoo.exceptions import UserError  # Necesario para el manejo de errores
import base64
from io import BytesIO
import xlsxwriter

class BankConciliationWizard(models.TransientModel):
    _name = 'bank.conciliation.wizard'
    _description = 'Bank Conciliation Wizard'

    date_from = fields.Date(string='Fecha Inicio', required=True, default=lambda self: self._get_first_day_of_current_month())
    date_to = fields.Date(string='Fecha Fin', required=True, default=lambda self: fields.Date.context_today(self) + timedelta(days=1))
    currency_id = fields.Many2one(comodel_name='res.currency', string='Moneda')
    company_id = fields.Many2one(comodel_name='res.company', string='Compañía', default=lambda self: self.env.company)
    journal_id = fields.Many2one('account.journal', string="Diario", required=True, domain="[('type', '=', 'bank')]")
    excel_file = fields.Binary("Archivo Excel", readonly=True)
    file_name = fields.Char("Nombre del Archivo")
    currency_option = fields.Selection([
        ('bs', 'Bolívares (Bs.)'),
        ('usd', 'Dólares ($)')
    ], string='Moneda', default='bs', required=True)

    def _get_first_day_of_current_month(self):
        today = fields.Date.context_today(self)
        first_day = today.replace(day=1)  # Cambia el día al primero del mes
        return first_day

    # def _prepare_data(self):
    #     # Dominio para filtrar las líneas contables relevantes
    #     domain = [
    #         ('date', '>=', self.date_from),
    #         ('date', '<=', self.date_to),
    #         ('company_id', '=', self.company_id.id),
    #         ('journal_id', '=', self.journal_id.id),
    #         ('move_id.state', '=', 'posted'),
    #     ]

    #     account_lines = self.env['account.move.line'].sudo().search(domain, order='date asc, id asc')

    #     # Consulta SQL para calcular el saldo inicial
    #     self.env.cr.execute("""
    #         WITH saldo_inicial_cte AS (
    #             SELECT 
    #                 SUM(
    #                     CASE 
    #                         WHEN payment.payment_type = 'inbound' THEN 
    #                             CASE 
    #                                 WHEN %s = 'bs' THEN debit
    #                                 ELSE debit_usd
    #                             END
    #                         WHEN payment.payment_type = 'outbound' THEN 
    #                             CASE 
    #                                 WHEN %s = 'bs' THEN -credit
    #                                 ELSE -credit_usd
    #                             END
    #                         ELSE 0
    #                     END
    #                 ) AS saldo_inicial
    #             FROM 
    #                 account_move_line aml
    #             LEFT JOIN account_move am ON aml.move_id = am.id
    #             LEFT JOIN account_payment payment ON am.payment_id = payment.id
    #             WHERE 
    #                 aml.date < %s
    #                 AND aml.company_id = %s
    #                 AND aml.journal_id = %s
    #                 AND am.state = 'posted'
    #         )
    #         SELECT saldo_inicial 
    #         FROM saldo_inicial_cte;
    #     """, (self.currency_option, self.currency_option, self.date_from, self.company_id.id, self.journal_id.id))

    #     saldo_inicial = self.env.cr.fetchone()[0] or 0

    #     # Inicializar variables
    #     results = []
    #     saldo_acumulado = saldo_inicial

    #     # Procesar las líneas contables
    #     for line in account_lines:
    #         payment_type = line.move_id.payment_id.payment_type if line.move_id.payment_id else None

    #         # Determinar valores según la moneda seleccionada
    #         if self.currency_option == 'bs':
    #             debit_value = line.debit
    #             credit_value = line.credit
    #         else:  # usd
    #             debit_value = line.debit_usd
    #             credit_value = line.credit_usd

    #         if payment_type == 'outbound' and credit_value > 0:
    #             # Restar créditos en pagos salientes
    #             saldo_acumulado -= credit_value
    #             results.append({
    #                 'date': line.date,
    #                 'account': line.account_id.name,
    #                 'partner': line.partner_id.name if line.partner_id else '',
    #                 'reference': line.move_id.ref,
    #                 'description': line.name,
    #                 'debit': debit_value,
    #                 'credit': credit_value,
    #                 'saldo': saldo_acumulado,
    #             })
    #         elif payment_type == 'inbound' and debit_value > 0:
    #             # Sumar débitos en pagos entrantes
    #             saldo_acumulado += debit_value
    #             results.append({
    #                 'date': line.date,
    #                 'account': line.account_id.name,
    #                 'partner': line.partner_id.name if line.partner_id else '',
    #                 'reference': line.move_id.ref,
    #                 'description': line.name,
    #                 'debit': debit_value,
    #                 'credit': credit_value,
    #                 'saldo': saldo_acumulado,
    #             })

    #     # Validar si no se encontraron resultados
    #     if not results:
    #         raise UserError('No se encontraron registros en el rango de fechas seleccionado.')

    #     # Preparar datos finales para el reporte
    #     saldo_final = saldo_acumulado
    #     return {
    #         'items': results,
    #         'company': self.company_id.name,
    #         'journal': self.journal_id.name,
    #         'account_code': self.journal_id.default_account_id.code,
    #         'account_name': self.journal_id.default_account_id.name,
    #         'currency': 'Bs.' if self.currency_option == 'bs' else '$',  # Actualizado para mostrar el símbolo correcto
    #         'date_from': self.date_from,
    #         'date_to': self.date_to,
    #         'saldo_inicial': saldo_inicial,
    #         'saldo_final': saldo_final,
    #     }

    def _prepare_data(self):
        # Dominio para filtrar las líneas contables relevantes y solo de la cuenta configurada en el diario
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
            ('journal_id', '=', self.journal_id.id),
            ('move_id.state', '=', 'posted'),
            ('account_id', '=', self.journal_id.default_account_id.id),  # Solo la cuenta del diario
        ]

        account_lines = self.env['account.move.line'].sudo().search(domain, order='date asc, id asc')

        # Consulta SQL para calcular el saldo inicial solo con la cuenta del diario
        self.env.cr.execute("""
            SELECT 
                SUM(
                    CASE 
                        WHEN %s = 'bs' THEN debit - credit
                        ELSE debit_usd - credit_usd
                    END
                ) AS saldo_inicial
            FROM 
                account_move_line aml
            WHERE 
                aml.date < %s
                AND aml.company_id = %s
                AND aml.journal_id = %s
                AND aml.account_id = %s
                AND EXISTS (
                    SELECT 1 FROM account_move am WHERE am.id = aml.move_id AND am.state = 'posted'
                )
        """, (self.currency_option, self.date_from, self.company_id.id, self.journal_id.id, self.journal_id.default_account_id.id))

        saldo_inicial = self.env.cr.fetchone()[0] or 0

        # Inicializar variables
        results = []
        saldo_acumulado = saldo_inicial

        # Procesar las líneas contables sin importar si son "inbound" o "outbound"
        for line in account_lines:
            debit_value = line.debit if self.currency_option == 'bs' else line.debit_usd
            credit_value = line.credit if self.currency_option == 'bs' else line.credit_usd

            saldo_acumulado += debit_value - credit_value  # Sumar débitos, restar créditos

            results.append({
                'date': line.date,
                'account': line.account_id.name,
                'partner': line.partner_id.name if line.partner_id else '',
                'reference': line.move_id.ref,
                'description': line.name,
                'debit': debit_value,
                'credit': credit_value,
                'saldo': saldo_acumulado,
            })

        # Validar si no se encontraron resultados
        if not results:
            raise UserError('No se encontraron registros en el rango de fechas seleccionado.')

        # Preparar datos finales para el reporte
        saldo_final = saldo_acumulado
        return {
            'items': results,
            'company': self.company_id.name,
            'journal': self.journal_id.name,
            'account_code': self.journal_id.default_account_id.code,
            'account_name': self.journal_id.default_account_id.name,
            'currency': 'Bs.' if self.currency_option == 'bs' else '$',
            'date_from': self.date_from,
            'date_to': self.date_to,
            'saldo_inicial': saldo_inicial,
            'saldo_final': saldo_final,
        }
        
    def print_pdf(self):
        data = self._prepare_data()
        return self.env.ref('gchakao_custom.action_report_bank_conciliation').report_action(self, data=data)

    def generate_excel_report(self):
        """Genera un archivo Excel de conciliación bancaria y lo prepara para descarga."""
        data = self._prepare_data()

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Diario de Banco')
        bold = workbook.add_format({'bold': True})

        # Estilos
        title_format = workbook.add_format({'bold': True, 'align': 'center', 'font_size': 14})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#FF0000', 'border': 1, 'align': 'center'})
        cell_format = workbook.add_format({'border': 1, 'align': 'left'})
        currency_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00', 'align': 'right'})

        # Título del Reporte (Fila 2)
        worksheet.merge_range('B2:F2', 'DIARIO DE BANCO', title_format)
        worksheet.merge_range('H2:I2', 'GRUPO CHAKAO', title_format)

        # Fila en blanco entre el título y los encabezados
        # Encabezados del Reporte (Inicia en columna B, fila 4)
        worksheet.write(3, 1, 'Empresa', header_format)
        worksheet.write(3, 2, data['company'], cell_format)

        worksheet.write(4, 1, 'Banco', header_format)
        worksheet.write(4, 2, data['journal'], cell_format)

        worksheet.write(5, 1, 'Cuenta Contable', header_format)
        worksheet.write(5, 2, f"{data['account_code']} - {data['account_name']}", cell_format)

        worksheet.write(6, 1, 'Fecha Inicio', header_format)
        worksheet.write(6, 2, str(data['date_from']), cell_format)

        worksheet.write(7, 1, 'Fecha Fin', header_format)
        worksheet.write(7, 2, str(data['date_to']), cell_format)

        worksheet.write(8, 1, 'Saldo Inicial', header_format)
        worksheet.write(8, 2, data['saldo_inicial'], currency_format)

        worksheet.write(9, 1, 'Saldo Final', header_format)
        worksheet.write(9, 2, data['saldo_final'], currency_format)

        # Fila en blanco entre los encabezados y la tabla
        # Tabla de Detalles (Inicia en fila 11)
        start_row = 11
        headers = ['Fecha', 'Cuenta', 'Cliente/Proveedor', 'Referencia', 'Descripción', 'Debe', 'Haber', 'Saldo']
        for col, header in enumerate(headers, start=1):  # Empieza en columna B
            worksheet.write(start_row, col, header, header_format)

        # Registros de datos (Inicia en fila 13)
        for idx, item in enumerate(data['items'], start=start_row + 1):
            worksheet.write(idx, 1, str(item['date']), cell_format)
            worksheet.write(idx, 2, item['account'], cell_format)
            worksheet.write(idx, 3, item['partner'], cell_format)
            worksheet.write(idx, 4, item['reference'], cell_format)
            worksheet.write(idx, 5, item['description'], cell_format)
            worksheet.write(idx, 6, item['debit'], currency_format)
            worksheet.write(idx, 7, item['credit'], currency_format)
            worksheet.write(idx, 8, item['saldo'], currency_format)

        # Ajustar el ancho de las columnas para mejorar legibilidad
        worksheet.set_column(1, 1, 20)  # Fecha
        worksheet.set_column(2, 2, 30)  # Cuenta
        worksheet.set_column(3, 3, 25)  # Cliente/Proveedor
        worksheet.set_column(4, 4, 20)  # Referencia
        worksheet.set_column(5, 5, 45)  # Descripción
        worksheet.set_column(6, 8, 15)  # Valores Monetario

        workbook.close()
        output.seek(0)
        excel_data = output.read()
        output.close()

        # Adjuntar archivo al asistente
        self.excel_file = base64.b64encode(excel_data)
        self.file_name = f"Diario_de_banco_{self.date_from}_a_{self.date_to}.xlsx"
        
        return {
            'type': 'ir.actions.act_url',
            'url': f"web/content/?model={self._name}&id={self.id}&field=excel_file&download=true&filename={self.file_name}",
            'target': 'self',
        }
