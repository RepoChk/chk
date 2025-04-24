from odoo import models, fields, api
from datetime import timedelta
from odoo.exceptions import UserError
import base64
from io import BytesIO
import xlsxwriter
import logging

_logger = logging.getLogger(__name__)

class VatSummaryWizard(models.TransientModel):
    _name = 'vat.summary.wizard'
    _description = 'Resumen de Análisis de Impuestos Nacionales'

    date_from = fields.Date(string='Fecha Inicio', required=True, 
                           default=lambda self: self._get_first_day_of_current_month())
    date_to = fields.Date(string='Fecha Fin', required=True, 
                         default=lambda self: fields.Date.context_today(self))
    currency_option = fields.Selection([
        ('bs', 'Bolívares (Bs.)'),
        ('usd', 'Dólares ($)')
    ], string='Moneda', default='bs', required=True)
    company_id = fields.Many2one('res.company', string='Compañía', 
                                default=lambda self: self.env.company)
    journal_ids = fields.Many2many('account.journal', string='Diarios', 
                                 domain="[('company_id', '=', company_id)]")
    excel_file = fields.Binary('Archivo Excel')
    file_name = fields.Char('Nombre del archivo')

    def _get_first_day_of_current_month(self):
        today = fields.Date.context_today(self)
        return today.replace(day=1)

    def _get_previous_excess(self, date_from):
        """Calcula el excedente de crédito fiscal del período anterior"""
        query = """
            SELECT COALESCE(SUM(balance), 0) as balance
            FROM account_move_line aml
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aa.code = '12201006'
            AND aml.date < %s
            AND aml.company_id = %s
        """
        self.env.cr.execute(query, (date_from, self.company_id.id))
        return self.env.cr.fetchone()[0]

    def _calculate_igtf(self, move):
        """
        Calcula el IGTF para una factura específica considerando solo los pagos reconciliados
        """
        igtf_total = 0
        
        try:
            # Obtener las líneas reconciliadas
            reconciled_lines = move.line_ids.filtered(
                lambda line: line.account_id.account_type in ['asset_receivable', 'liability_payable']
            )
            
            # Obtener las conciliaciones parciales
            partial_reconciles = self.env['account.partial.reconcile'].search([
                '|',
                ('credit_move_id', 'in', reconciled_lines.ids),
                ('debit_move_id', 'in', reconciled_lines.ids)
            ])

            # Obtener los pagos únicos
            payments = self.env['account.payment']
            for reconcile in partial_reconciles:
                if reconcile.credit_move_id.payment_id:
                    payments |= reconcile.credit_move_id.payment_id
                if reconcile.debit_move_id.payment_id:
                    payments |= reconcile.debit_move_id.payment_id

            # Calcular IGTF para cada pago
            for payment in payments:
                if payment.aplicar_igtf_divisa and payment.mount_igtf:
                    # El mount_igtf siempre está en USD, solo convertir si el reporte es en BS
                    if self.currency_option == 'bs':
                        igtf_total += payment.mount_igtf * move.tax_today
                    else:
                        igtf_total += payment.mount_igtf

        except Exception as e:
            _logger.error(f"Error calculando IGTF para la factura {move.name}: {str(e)}")
            return 0.0

        return round(igtf_total, 2)

    def _get_vat_summary_data(self):
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]

        if self.journal_ids:
            domain.append(('journal_id', 'in', self.journal_ids.ids))
        
        sales_moves = self.env['account.move'].search(
            domain + [('move_type', 'in', ['out_invoice', 'out_refund'])])
        purchase_moves = self.env['account.move'].search(
            domain + [('move_type', 'in', ['in_invoice', 'in_refund'])])

        ventas_data = []
        compras_data = []
        totales_ventas = {
            'total': 0,
            'base_imponible': 0,
            'exento': 0,
            'iva': 0,
            'iva_retenido': 0,
            'igtf': 0
        }
        totales_compras = {
            'total': 0,
            'base_imponible': 0,
            'exento': 0,
            'iva': 0,
            'iva_retenido': 0,
            'islr_retenido': 0
        }

        # Inicializar los acumuladores para ventas
        acumuladores_ventas = {
            'ventas_exentas': 0,
            'ventas_gravadas_general16': 0,
            'ventas_gravadas_general31': 0,
            'ventas_gravadas_general8': 0,
            'ventas_gravadas16_tax': 0,
            'ventas_gravadas31_tax': 0,
            'ventas_gravadas8_tax': 0
        }

        # Inicializar los acumuladores para compras
        acumuladores_compras = {
            'compras_exentas': 0,
            'compras_gravadas_general16': 0,
            'importacion_gravadas_general16': 0,
            'compras_gravadas_general31': 0,
            'compras_gravadas_general8': 0,
            'compras_gravadas16_tax': 0,
            'importacion_gravadas16_tax': 0,
            'compras_gravadas31_tax': 0,
            'compras_gravadas8_tax': 0
        }

        # Procesar ventas
        for move in sales_moves:
            currency_is_ves = move.currency_id.name == 'VES' or 'VEF'
            
            # Cálculo de montos según la moneda seleccionada
            if self.currency_option == 'bs':
                if currency_is_ves:
                    total = sum(line.price_subtotal for line in move.invoice_line_ids)
                    base_imponible = sum(line.price_subtotal 
                                       for line in move.invoice_line_ids 
                                       if any(tax.amount > 0 for tax in line.tax_ids))
                    exento = sum(line.price_subtotal 
                               for line in move.invoice_line_ids 
                               if all(tax.amount == 0 for tax in line.tax_ids))
                else:
                    total = sum(line.price_subtotal_usd * move.tax_today for line in move.invoice_line_ids)
                    base_imponible = sum(line.price_subtotal_usd * move.tax_today
                                       for line in move.invoice_line_ids 
                                       if any(tax.amount > 0 for tax in line.tax_ids))
                    exento = sum(line.price_subtotal_usd * move.tax_today
                               for line in move.invoice_line_ids 
                               if all(tax.amount == 0 for tax in line.tax_ids))
            else:  # USD
                if currency_is_ves:
                    total = sum(line.price_subtotal / move.tax_today for line in move.invoice_line_ids)
                    base_imponible = sum(line.price_subtotal / move.tax_today
                                       for line in move.invoice_line_ids 
                                       if any(tax.amount > 0 for tax in line.tax_ids))
                    exento = sum(line.price_subtotal / move.tax_today
                               for line in move.invoice_line_ids 
                               if all(tax.amount == 0 for tax in line.tax_ids))
                else:
                    total = sum(line.price_subtotal_usd for line in move.invoice_line_ids)
                    base_imponible = sum(line.price_subtotal_usd
                                       for line in move.invoice_line_ids 
                                       if any(tax.amount > 0 for tax in line.tax_ids))
                    exento = sum(line.price_subtotal_usd
                               for line in move.invoice_line_ids 
                               if all(tax.amount == 0 for tax in line.tax_ids))

            # Cálculo del IVA
            if self.currency_option == 'bs':
                if currency_is_ves:
                    iva = sum(tax.amount/100 * line.price_subtotal
                             for line in move.invoice_line_ids
                             for tax in line.tax_ids
                             if tax.amount > 0)
                else:
                    iva = sum(tax.amount/100 * line.price_subtotal_usd * move.tax_today
                             for line in move.invoice_line_ids
                             for tax in line.tax_ids
                             if tax.amount > 0)
            else:  # USD
                if currency_is_ves:
                    iva = sum(tax.amount/100 * line.price_subtotal / move.tax_today
                             for line in move.invoice_line_ids
                             for tax in line.tax_ids
                             if tax.amount > 0)
                else:
                    iva = sum(tax.amount/100 * line.price_subtotal_usd
                             for line in move.invoice_line_ids
                             for tax in line.tax_ids
                             if tax.amount > 0)

            # Retención de IVA para ventas
            iva_retenido = 0
            for wh in move.wh_iva_id:
                wh_currency_is_ves = wh.currency_id.name == 'VES' or 'VEF'
                if self.currency_option == 'bs':
                    if wh_currency_is_ves:
                        iva_retenido += wh.total_tax_ret
                    else:
                        iva_retenido += wh.total_tax_ret * move.tax_today
                else:  # USD
                    if wh_currency_is_ves:
                        iva_retenido += wh.total_tax_ret / move.tax_today
                    else:
                        iva_retenido += wh.total_tax_ret

            # Cálculo del IGTF
            igtf = self._calculate_igtf(move)

            valores_ventas = {
                'fecha': move.date.strftime('%d/%m/%y'),
                'factura': move.invoice_number or move.name,
                'total': round(total, 2),
                'base_imponible': round(base_imponible, 2),
                'exento': round(exento, 2),
                'iva': round(iva, 2),
                'iva_retenido': round(iva_retenido, 2),
                'igtf': igtf
            }
            
            ventas_data.append(valores_ventas)
            for key in totales_ventas:
                totales_ventas[key] += valores_ventas[key] if isinstance(valores_ventas.get(key), (int, float)) else 0

            # Agregar esta parte para los acumuladores
            for line in move.invoice_line_ids:
                amount = 0
                if self.currency_option == 'bs':
                    if move.currency_id.name in ['VES', 'VEF']:
                        amount = line.price_subtotal
                    else:
                        amount = line.price_subtotal_usd * move.tax_today
                else:  # USD
                    if move.currency_id.name in ['VES', 'VEF']:
                        amount = line.price_subtotal / move.tax_today
                    else:
                        amount = line.price_subtotal_usd

                # Clasificar según el impuesto
                if not line.tax_ids or all(tax.amount == 0 for tax in line.tax_ids):
                    acumuladores_ventas['ventas_exentas'] += amount
                else:
                    for tax in line.tax_ids:
                        if tax.amount == 16.00:
                            acumuladores_ventas['ventas_gravadas_general16'] += amount
                            acumuladores_ventas['ventas_gravadas16_tax'] += amount * 0.16
                        elif tax.amount == 31.00:
                            acumuladores_ventas['ventas_gravadas_general31'] += amount
                            acumuladores_ventas['ventas_gravadas31_tax'] += amount * 0.31
                        elif tax.amount == 8.00:
                            acumuladores_ventas['ventas_gravadas_general8'] += amount
                            acumuladores_ventas['ventas_gravadas8_tax'] += amount * 0.08

        # Procesar compras
        for move in purchase_moves:
            currency_is_ves = move.currency_id.name == 'VES' or 'VEF'
            
            # Cálculo de montos según la moneda seleccionada
            if self.currency_option == 'bs':
                if currency_is_ves:
                    total = sum(line.price_subtotal for line in move.invoice_line_ids)
                    base_imponible = sum(line.price_subtotal 
                                       for line in move.invoice_line_ids 
                                       if any(tax.amount > 0 for tax in line.tax_ids))
                    exento = sum(line.price_subtotal 
                               for line in move.invoice_line_ids 
                               if all(tax.amount == 0 for tax in line.tax_ids))
                else:
                    total = sum(line.price_subtotal_usd * move.tax_today for line in move.invoice_line_ids)
                    base_imponible = sum(line.price_subtotal_usd * move.tax_today
                                       for line in move.invoice_line_ids 
                                       if any(tax.amount > 0 for tax in line.tax_ids))
                    exento = sum(line.price_subtotal_usd * move.tax_today
                               for line in move.invoice_line_ids 
                               if all(tax.amount == 0 for tax in line.tax_ids))
            else:  # USD
                if currency_is_ves:
                    total = sum(line.price_subtotal / move.tax_today for line in move.invoice_line_ids)
                    base_imponible = sum(line.price_subtotal / move.tax_today
                                       for line in move.invoice_line_ids 
                                       if any(tax.amount > 0 for tax in line.tax_ids))
                    exento = sum(line.price_subtotal / move.tax_today
                               for line in move.invoice_line_ids 
                               if all(tax.amount == 0 for tax in line.tax_ids))
                else:
                    total = sum(line.price_subtotal_usd for line in move.invoice_line_ids)
                    base_imponible = sum(line.price_subtotal_usd
                                       for line in move.invoice_line_ids 
                                       if any(tax.amount > 0 for tax in line.tax_ids))
                    exento = sum(line.price_subtotal_usd
                               for line in move.invoice_line_ids 
                               if all(tax.amount == 0 for tax in line.tax_ids))

            # Cálculo del IVA
            if self.currency_option == 'bs':
                if currency_is_ves:
                    iva = sum(tax.amount/100 * line.price_subtotal
                             for line in move.invoice_line_ids
                             for tax in line.tax_ids
                             if tax.amount > 0)
                else:
                    iva = sum(tax.amount/100 * line.price_subtotal_usd * move.tax_today
                             for line in move.invoice_line_ids
                             for tax in line.tax_ids
                             if tax.amount > 0)
            else:  # USD
                if currency_is_ves:
                    iva = sum(tax.amount/100 * line.price_subtotal / move.tax_today
                             for line in move.invoice_line_ids
                             for tax in line.tax_ids
                             if tax.amount > 0)
                else:
                    iva = sum(tax.amount/100 * line.price_subtotal_usd
                             for line in move.invoice_line_ids
                             for tax in line.tax_ids
                             if tax.amount > 0)

            # Retención de IVA para compras
            iva_retenido = 0
            for wh in move.wh_iva_id:
                wh_currency_is_ves = wh.currency_id.name == 'VES' or 'VEF'
                if self.currency_option == 'bs':
                    if wh_currency_is_ves:
                        iva_retenido += wh.total_tax_ret
                    else:
                        iva_retenido += wh.total_tax_ret * move.tax_today
                else:  # USD
                    if wh_currency_is_ves:
                        iva_retenido += wh.total_tax_ret / move.tax_today
                    else:
                        iva_retenido += wh.total_tax_ret

            # Retención de ISLR para compras
            islr_retenido = 0
            for doc in move.islr_wh_doc_id:
                doc_currency_is_ves = doc.currency_id.name == 'VES' or 'VEF'
                if self.currency_option == 'bs':
                    if doc_currency_is_ves:
                        islr_retenido += doc.amount_total_ret
                    else:
                        islr_retenido += doc.amount_total_ret * move.tax_today
                else:  # USD
                    if doc_currency_is_ves:
                        islr_retenido += doc.amount_total_ret / move.tax_today
                    else:
                        islr_retenido += doc.amount_total_ret

            valores_compras = {
                'fecha': move.date.strftime('%d/%m/%y'),
                'factura': move.supplier_invoice_number or move.name,
                'total': round(total, 2),
                'base_imponible': round(base_imponible, 2),
                'exento': round(exento, 2),
                'iva': round(iva, 2),
                'iva_retenido': round(iva_retenido, 2),
                'islr_retenido': round(islr_retenido, 2)
            }
            
            compras_data.append(valores_compras)
            for key in totales_compras:
                totales_compras[key] += valores_compras[key] if isinstance(valores_compras.get(key), (int, float)) else 0

            # Agregar esta parte para los acumuladores
            for line in move.invoice_line_ids:
                amount = 0
                if self.currency_option == 'bs':
                    if move.currency_id.name in ['VES', 'VEF']:
                        amount = line.price_subtotal
                    else:
                        amount = line.price_subtotal_usd * move.tax_today
                else:  # USD
                    if move.currency_id.name in ['VES', 'VEF']:
                        amount = line.price_subtotal / move.tax_today
                    else:
                        amount = line.price_subtotal_usd

                # Clasificar según el impuesto
                if not line.tax_ids or all(tax.amount == 0 for tax in line.tax_ids):
                    acumuladores_compras['compras_exentas'] += amount
                else:
                    for tax in line.tax_ids:
                        if tax.amount == 16.00 and move.partner_id.people_type_company != 'pjnd':
                            acumuladores_compras['compras_gravadas_general16'] += amount
                            acumuladores_compras['compras_gravadas16_tax'] += amount * 0.16
                        elif tax.amount == 31.00 and move.partner_id.people_type_company != 'pjnd':
                            acumuladores_compras['compras_gravadas_general31'] += amount
                            acumuladores_compras['compras_gravadas31_tax'] += amount * 0.31
                        elif tax.amount == 8.00 and move.partner_id.people_type_company != 'pjnd':
                            acumuladores_compras['compras_gravadas_general8'] += amount
                            acumuladores_compras['compras_gravadas8_tax'] += amount * 0.08
                        elif tax.amount == 16.00 and move.partner_id.people_type_company == 'pjnd':
                            acumuladores_compras['importacion_gravadas_general16'] += amount
                            acumuladores_compras['importacion_gravadas16_tax'] += amount * 0.16

        # Obtener el excedente de crédito fiscal del período anterior
        excedente_anterior = self._get_previous_excess(self.date_from)
        if self.currency_option == 'usd':
            today_rate = self.env['res.currency.rate'].search([
                ('currency_id.name', '=', 'USD'),
                ('name', '<=', fields.Date.today())
            ], limit=1, order='name desc').rate
            if today_rate:
                excedente_anterior /= today_rate

        # Actualizar el resumen_ventas existente con los nuevos valores
        resumen_ventas = {
            'ventas_exentas': acumuladores_ventas['ventas_exentas'],
            'ventas_gravadas_general16': acumuladores_ventas['ventas_gravadas_general16'],
            'ventas_gravadas16_tax': acumuladores_ventas['ventas_gravadas16_tax'],
            'ventas_gravadas_general31': acumuladores_ventas['ventas_gravadas_general31'],
            'ventas_gravadas31_tax': acumuladores_ventas['ventas_gravadas31_tax'],
            'ventas_gravadas_general8': acumuladores_ventas['ventas_gravadas_general8'],
            'ventas_gravadas8_tax': acumuladores_ventas['ventas_gravadas8_tax'],
            'total_ventas': acumuladores_ventas['ventas_exentas'] + acumuladores_ventas['ventas_gravadas_general16'] +
            acumuladores_ventas['ventas_gravadas_general31'] + acumuladores_ventas['ventas_gravadas_general8'],
            'total_debito_fiscal': acumuladores_ventas['ventas_gravadas16_tax'] + acumuladores_ventas['ventas_gravadas31_tax'] +
            acumuladores_ventas['ventas_gravadas8_tax'],
            'total_retenciones': totales_ventas['iva_retenido'],
            'anticipo_islr': (acumuladores_ventas['ventas_exentas'] + acumuladores_ventas['ventas_gravadas_general16'] +
            acumuladores_ventas['ventas_gravadas_general31'] + acumuladores_ventas['ventas_gravadas_general8']) * 0.01,
            'igtf': totales_ventas['igtf']
        }

        # Resumen de compras
        resumen_compras = {
            'compras_exentas': acumuladores_compras['compras_exentas'],
            'compras_gravadas_general16': acumuladores_compras['compras_gravadas_general16'],
            'compras_gravadas16_tax': acumuladores_compras['compras_gravadas16_tax'],
            'importacion_gravadas_general16': acumuladores_compras['importacion_gravadas_general16'],
            'importacion_gravadas16_tax': acumuladores_compras['importacion_gravadas16_tax'],
            'compras_gravadas_general31': acumuladores_compras['compras_gravadas_general31'],
            'compras_gravadas31_tax': acumuladores_compras['compras_gravadas31_tax'],
            'compras_gravadas_general8': acumuladores_compras['compras_gravadas_general8'],
            'compras_gravadas8_tax': acumuladores_compras['compras_gravadas8_tax'],
            'total_compras': acumuladores_compras['compras_exentas'] + acumuladores_compras['compras_gravadas_general16'] +
            acumuladores_compras['compras_gravadas_general31'] + acumuladores_compras['compras_gravadas_general8'] +
            acumuladores_compras['importacion_gravadas_general16'],
            'total_credito_fiscal': acumuladores_compras['compras_gravadas16_tax'] + acumuladores_compras['importacion_gravadas16_tax'] +
            acumuladores_compras['compras_gravadas31_tax'] + acumuladores_compras['compras_gravadas8_tax'],
            'total_compras_nacionales': acumuladores_compras['compras_exentas'] + acumuladores_compras['compras_gravadas_general16'] +
            acumuladores_compras['compras_gravadas_general31'] + acumuladores_compras['compras_gravadas_general8'],
            'total_compras_nacionales_tax': acumuladores_compras['compras_gravadas16_tax'] + 
            acumuladores_compras['compras_gravadas31_tax'] + acumuladores_compras['compras_gravadas8_tax'],
            'total_retenciones_iva': totales_compras['iva_retenido'],
            'total_retenciones_islr': totales_compras['islr_retenido']
        }

        # Resumen IVA del período
        resumen_iva = {
            'excedente_anterior': excedente_anterior,
            'iva_pagar': excedente_anterior - (resumen_ventas['total_debito_fiscal'] + resumen_ventas['total_retenciones'] + resumen_compras['importacion_gravadas16_tax'] + resumen_compras['total_compras_nacionales_tax'])
        }

        return {
            'ventas': ventas_data or [],
            'compras': compras_data or [],
            'totales_ventas': totales_ventas,
            'totales_compras': totales_compras,
            'resumen_ventas': resumen_ventas,
            'resumen_compras': resumen_compras,
            'resumen_iva': resumen_iva,
            'moneda': 'Bs.' if self.currency_option == 'bs' else '$',
            'date_from': self.date_from.strftime('%d/%m/%y'),
            'date_to': self.date_to.strftime('%d/%m/%y'),
        }

    def generate_pdf_report(self):
        vat_summary_data = self._get_vat_summary_data()
        return self.env.ref('gchakao_custom.action_report_vat_summary').with_context(
            paperformat_id=self.env.ref('gchakao_custom.paperformat_vat_summary').id,
            **vat_summary_data
        ).report_action(self)

    def generate_excel_report(self):
        """Genera el archivo Excel con los datos del Resumen de IVA."""
        data = self._get_vat_summary_data()
        
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Resumen IVA')

        # Formatos
        title_format = workbook.add_format({
            'bold': True, 
            'align': 'center',
            'font_size': 12,
            'text_wrap': True
        })
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'bg_color': '#C9C9C9',
            'border': 1,
            'text_wrap': True
        })
        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'text_wrap': True
        })
        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.00',
            'text_wrap': True
        })
        total_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'right',
            'bg_color': '#C9C9C9',
            'num_format': '#,##0.00',
            'text_wrap': True
        })

        # Agregar formato para totales con fondo gris
        total_row_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'left',
            'bg_color': '#C9C9C9',
            'text_wrap': True
        })
        
        total_number_bold_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.00',
            'text_wrap': True
        })

        # Configurar anchos de columna (empezando desde la columna B)
        worksheet.set_column('A:A', 2)   # Margen
        worksheet.set_column('B:B', 12)  # Fecha
        worksheet.set_column('C:C', 20)  # Número de Factura
        worksheet.set_column('D:I', 15)  # Columnas numéricas ventas
        worksheet.set_column('J:J', 12)  # Fecha
        worksheet.set_column('K:K', 20)  # Número de Factura
        worksheet.set_column('L:Q', 15)  # Columnas numéricas compras
        
        # Altura de fila para el margen superior
        worksheet.set_row(0, 20)

        # Título y encabezado (empezando desde fila 2 y columna B)
        row = 2
        worksheet.merge_range(f'B{row}:Q{row}', 'Resumen para Análisis de Impuestos Nacionales', title_format)
        row += 1
        
        # Corregimos el formato de la fecha
        fecha_desde = self.date_from.strftime("%d/%m/%Y")
        fecha_hasta = self.date_to.strftime("%d/%m/%Y")
        moneda = "Bolívares" if self.currency_option == "bs" else "Dólares"
        
        worksheet.merge_range(
            f'B{row}:Q{row}', 
            f'Período Desde: {fecha_desde} Hasta: {fecha_hasta} - Moneda: {moneda}', 
            title_format
        )

        # Encabezados de columnas
        row += 2
        # Encabezado Ventas y Compras
        worksheet.merge_range(f'B{row}:I{row}', 'Ventas', header_format)
        worksheet.merge_range(f'J{row}:Q{row}', 'Compras', header_format)
        
        ventas_headers = ['Fecha', 'Factura', 'Total', 'Base Imp.', 'Exento', 'I.V.A.', 'I.V.A. Ret.', 'IGTF']
        compras_headers = ['Fecha', 'Factura', 'Total', 'Base Imp.', 'Exento', 'I.V.A.', 'I.V.A. Ret.', 'I.S.L.R. Ret.']
        
        col = 1  # Empezar desde columna B
        for header in ventas_headers:
            worksheet.write(row, col, header, header_format)
            col += 1
        
        for header in compras_headers:
            worksheet.write(row, col, header, header_format)
            col += 1

        # Datos
        row += 1
        start_data_row = row
        
        # Escribir datos de ventas y compras
        max_rows = max(len(data['ventas']), len(data['compras']))
        for i in range(max_rows):
            # Ventas
            if i < len(data['ventas']):
                venta = data['ventas'][i]
                worksheet.write(row, 1, venta['fecha'], cell_format)
                worksheet.write(row, 2, venta['factura'], cell_format)
                worksheet.write(row, 3, venta['total'], number_format)
                worksheet.write(row, 4, venta['base_imponible'], number_format)
                worksheet.write(row, 5, venta['exento'], number_format)
                worksheet.write(row, 6, venta['iva'], number_format)
                worksheet.write(row, 7, venta['iva_retenido'], number_format)
                worksheet.write(row, 8, venta['igtf'], number_format)

            # Compras
            if i < len(data['compras']):
                compra = data['compras'][i]
                worksheet.write(row, 9, compra['fecha'], cell_format)
                worksheet.write(row, 10, compra['factura'], cell_format)
                worksheet.write(row, 11, compra['total'], number_format)
                worksheet.write(row, 12, compra['base_imponible'], number_format)
                worksheet.write(row, 13, compra['exento'], number_format)
                worksheet.write(row, 14, compra['iva'], number_format)
                worksheet.write(row, 15, compra['iva_retenido'], number_format)
                worksheet.write(row, 16, compra['islr_retenido'], number_format)
            
            row += 1
        
        row += 1
        # Totales
        worksheet.merge_range(f'B{row}:C{row}', 'Total', header_format)
        worksheet.merge_range(f'J{row}:K{row}', 'Total', header_format)
        
        row -= 1
        # Totales Ventas
        worksheet.write(row, 3, data['totales_ventas']['total'], total_format)
        worksheet.write(row, 4, data['totales_ventas']['base_imponible'], total_format)
        worksheet.write(row, 5, data['totales_ventas']['exento'], total_format)
        worksheet.write(row, 6, data['totales_ventas']['iva'], total_format)
        worksheet.write(row, 7, data['totales_ventas']['iva_retenido'], total_format)
        worksheet.write(row, 8, data['totales_ventas']['igtf'], total_format)
        
        # Totales Compras
        worksheet.write(row, 11, data['totales_compras']['total'], total_format)
        worksheet.write(row, 12, data['totales_compras']['base_imponible'], total_format)
        worksheet.write(row, 13, data['totales_compras']['exento'], total_format)
        worksheet.write(row, 14, data['totales_compras']['iva'], total_format)
        worksheet.write(row, 15, data['totales_compras']['iva_retenido'], total_format)
        worksheet.write(row, 16, data['totales_compras']['islr_retenido'], total_format)

        row += 2

        # Tablas de Resumen
        row = self._write_sales_summary(workbook, worksheet, row, data)
        row = self._write_purchases_summary(workbook, worksheet, row, data)
        self._write_vat_summary(workbook, worksheet, row, data)

        workbook.close()
        output.seek(0)

        # Guardar archivo en campo binary
        self.excel_file = base64.b64encode(output.read())
        self.file_name = f"Resumen_IVA_{self.date_from}_{self.date_to}.xlsx"

        return {
            'type': 'ir.actions.act_url',
            'url': f"web/content/?model={self._name}&id={self.id}&field=excel_file&download=true&filename={self.file_name}",
            'target': 'self',
        }
        
    def _write_sales_summary(self, workbook, worksheet, start_row, data):
        """Escribe la tabla de resumen de ventas"""
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'bg_color': '#C9C9C9',
            'border': 1,
            'text_wrap': True
        })
        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'text_wrap': True
        })
        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.00',
            'text_wrap': True
        })
        # Agregar los formatos que faltaban
        total_row_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'left',
            'bg_color': '#C9C9C9',
            'text_wrap': True
        })
        total_number_bold_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.00',
            'text_wrap': True
        })

        row = start_row + 3  # Mover 3 filas abajo para empezar
        worksheet.merge_range(f'D{row}:O{row}', 'RESUMEN DE VENTAS', header_format)
        row += 1
        
        # Encabezados (sin salto)
        worksheet.merge_range(f'D{row}:K{row}', 'Descripción', header_format)
        worksheet.merge_range(f'L{row}:M{row}', 'Base Imponible', header_format)
        worksheet.merge_range(f'N{row}:O{row}', 'Débito Fiscal', header_format)
        
        row += 1
        # Datos con formato especial para totales
        ventas_items = [
            ('Ventas Internas Exentas o Exoneradas', 
             data['resumen_ventas']['ventas_exentas'], 0, False),
            ('Ventas Internas Gravadas Alíc. Reducida (8%)', 
             data['resumen_ventas']['ventas_gravadas_general8'],
             data['resumen_ventas']['ventas_gravadas8_tax'], False),
            ('Ventas Internas Gravadas Alíc. General (16%)', 
             data['resumen_ventas']['ventas_gravadas_general16'],
             data['resumen_ventas']['ventas_gravadas16_tax'], False),
            ('Ventas Internas Gravadas Alíc. General + Alíc. Adicional (31%)', 
             data['resumen_ventas']['ventas_gravadas_general31'],
             data['resumen_ventas']['ventas_gravadas31_tax'], False),
            ('Ventas de Exportación', 0, 0, False),
            ('TOTAL VENTAS Y DÉBITOS FISCALES DEL PERÍODO', 
             data['resumen_ventas']['total_ventas'],
             data['resumen_ventas']['total_debito_fiscal'], True),
            ('TOTAL RETENCIONES DEL PERÍODO',
             data['resumen_ventas']['total_retenciones'], 0, True),
            ('ANTICIPO ISLR 1%',
             data['resumen_ventas']['anticipo_islr'], 0, True),
            ('IGTF',
             data['resumen_ventas']['igtf'], 0, True)
        ]

        for desc, base, debito, is_total in ventas_items:
            desc_format = total_row_format if is_total else cell_format
            num_format = total_number_bold_format if is_total else number_format
            
            worksheet.merge_range(f'D{row}:K{row}', desc, desc_format)
            worksheet.merge_range(f'L{row}:M{row}', base, num_format)
            worksheet.merge_range(f'N{row}:O{row}', debito, num_format)
            row += 1

        return row + 2

    def _write_purchases_summary(self, workbook, worksheet, start_row, data):
        """Escribe la tabla de resumen de compras"""
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'bg_color': '#C9C9C9',
            'border': 1,
            'text_wrap': True
        })
        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'text_wrap': True
        })
        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.00',
            'text_wrap': True
        })

        total_row_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'left',
            'bg_color': '#C9C9C9',
            'text_wrap': True
        })
        total_number_bold_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.00',
            'text_wrap': True
        })

        row = start_row
        worksheet.merge_range(f'D{row}:O{row}', 'RESUMEN DE COMPRAS', header_format)
        
        row += 1
        # Encabezados (sin salto)
        worksheet.merge_range(f'D{row}:K{row}', 'Descripción', header_format)
        worksheet.merge_range(f'L{row}:M{row}', 'Base Imponible', header_format)
        worksheet.merge_range(f'N{row}:O{row}', 'Crédito Fiscal', header_format)
        
        row += 1
        # Datos con formato especial para totales
        compras_items = [
            ('Compras Internas Exentas o Exoneradas',
             data['resumen_compras']['compras_exentas'], 0, False),
            ('Importación Gravadas por Alíc. General (16%)',
             data['resumen_compras']['importacion_gravadas_general16'],
             data['resumen_compras']['importacion_gravadas16_tax'], False),
            ('Compras Internas Gravadas Alíc. General (16%)',
             data['resumen_compras']['compras_gravadas_general16'],
             data['resumen_compras']['compras_gravadas16_tax'], False),
            ('Compras Internas Gravadas Alíc. General + Alíc. Adicional (31%)',
             data['resumen_compras']['compras_gravadas_general31'],
             data['resumen_compras']['compras_gravadas31_tax'], False),
            ('Compras Internas Gravadas Alíc. Reducida (8%)',
             data['resumen_compras']['compras_gravadas_general8'],
             data['resumen_compras']['compras_gravadas8_tax'], False),
            ('TOTAL',
             data['resumen_compras']['total_compras'],
             data['resumen_compras']['total_credito_fiscal'], True),
            ('TOTAL RETENCIONES IVA DEL PERÍODO',
             data['resumen_compras']['total_retenciones_iva'], 0, True),
            ('TOTAL RETENCIONES ISLR DEL PERÍODO',
             data['resumen_compras']['total_retenciones_islr'], 0, True)
        ]


        for desc, base, credito, is_total in compras_items:
            desc_format = total_row_format if is_total else cell_format
            num_format = total_number_bold_format if is_total else number_format
            
            worksheet.merge_range(f'D{row}:K{row}', desc, desc_format)
            worksheet.merge_range(f'L{row}:M{row}', base, num_format)
            worksheet.merge_range(f'N{row}:O{row}', credito, num_format)
            row += 1

        return row + 2

    def _write_vat_summary(self, workbook, worksheet, start_row, data):
        """Escribe la tabla de resumen de IVA del período"""
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'bg_color': '#C9C9C9',
            'border': 1,
            'text_wrap': True
        })
        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'text_wrap': True
        })
        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.00',
            'text_wrap': True
        })
        total_row_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'left',
            'bg_color': '#C9C9C9',
            'text_wrap': True
        })
        total_number_bold_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.00',
            'text_wrap': True
        })

        row = start_row
        worksheet.merge_range(f'D{row}:O{row}', 'RESUMEN IVA DEL PERÍODO', header_format)
        row += 1
        # Encabezados (sin salto)
        worksheet.merge_range(f'D{row}:K{row}', 'Descripción', header_format)
        worksheet.merge_range(f'L{row}:M{row}', 'Base Imponible', header_format)
        worksheet.merge_range(f'N{row}:O{row}', 'Débito/Crédito Fiscal', header_format)
        
        row += 1
        # Datos con formato especial para totales
        iva_items = [
            ('EXCEDENTE CRÉDITO FISCAL DEL PERÍODO ANTERIOR', 0,
             data['resumen_iva']['excedente_anterior'], False),
            ('TOTAL VTAS. Y DÉBI. FISCALES P/EFECTOS DE DETERM.',
             data['resumen_ventas']['total_ventas'],
             data['resumen_ventas']['total_debito_fiscal'], False),
            ('TOTAL RETENCIONES DEL PERÍODO', 0,
             data['resumen_ventas']['total_retenciones'], False),
            ('TOTAL IMPORTACIÓN GRAVADAS POR ALÍCUOTA GENERAL',
             data['resumen_compras']['importacion_gravadas_general16'],
             data['resumen_compras']['importacion_gravadas16_tax'], False),
            ('TOTAL COMPRAS Y CRÉDITOS FISCALES DEL PERÍODO',
             data['resumen_compras']['total_compras_nacionales'],
             data['resumen_compras']['total_compras_nacionales_tax'], False),
            ('TOTAL IVA A PAGAR', 0,
             data['resumen_iva']['iva_pagar'], True)
        ]

        for desc, base, monto, is_total in iva_items:
            desc_format = total_row_format if is_total else cell_format
            num_format = total_number_bold_format if is_total else number_format
            
            worksheet.merge_range(f'D{row}:K{row}', desc, desc_format)
            worksheet.merge_range(f'L{row}:M{row}', base, num_format)
            worksheet.merge_range(f'N{row}:O{row}', monto, num_format)
            row += 1