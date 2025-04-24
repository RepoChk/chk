# coding: utf-8
##############################################################################

###############################################################################
import time
import base64
import xlsxwriter
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMAT
from datetime import datetime, date, timedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from io import BytesIO

class FiscalBookWizard(models.TransientModel):
    """
    Sales book wizard implemented using the osv_memory wizard system
    """
    _inherit = "account.fiscal.book.wizard"

    @api.model
    def default_get(self, field_list):

        fiscal_book_obj = self.env['account.fiscal.book']
        fiscal_book = fiscal_book_obj.browse(self._context['active_id'])
        res = super(FiscalBookWizard, self).default_get(field_list)
        local_period = fiscal_book_obj.get_time_period(fiscal_book.time_period, fiscal_book)
        res.update({'type': fiscal_book.type})
        res.update({'date_start': local_period.get('dt_from', '')})
        res.update({'date_end': local_period.get('dt_to', '')})
        if fiscal_book.fortnight == 'first':
            date_obj = local_period.get('dt_to', '').split('-')
            res.update({'date_end': "%0004d-%02d-15" % (int(date_obj[0]), int(date_obj[1]))})
        elif fiscal_book.fortnight == 'second':
            date_obj = local_period.get('dt_to', '').split('-')
            res.update({'date_start': "%0004d-%02d-16" % (int(date_obj[0]), int(date_obj[1]))})
        return res

    def set_formatos(self, workbook):
       formatos = {}
       formatos['text'] = workbook.add_format({'num_format': '@'})
       return formatos

    def remove_hyphens(self, vat):
        """Remueve todos los guiones del string VAT solo si contiene guiones."""
        return vat.replace('-', '') if vat and '-' in vat else vat  

    def check_report_xlsx(self):
        if self.type == 'purchase':
            file_name = 'Libro_Compra.xlsx'
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True, 'strings_to_numbers': False})
            sheet = workbook.add_worksheet('Libro Compra')
            formats = self.set_formats(workbook)
            datos_compras, datos_compras_ajustes = self.get_datas_compras()
            if not datos_compras:
                raise UserError('No hay datos disponibles')
            sheet.merge_range('B3:G3', datos_compras[0]['company_name'], formats['string_titulo'])
            sheet.merge_range('M3:T3', 'Libro de Compras', formats['string_titulo'])
            sheet.merge_range('B4:G4', datos_compras[0]['company_rif'], formats['string'])
            sheet.merge_range('B5:G5', datos_compras[0]['company_street'], formats['string'])
            format_new = "%d/%m/%Y"
            date_start = datetime.strptime(str(self.date_start), DATE_FORMAT).date()
            date_end = datetime.strptime(str(self.date_end), DATE_FORMAT).date()

            sheet.merge_range('M4:N4', 'Desde', formats['string'])
            sheet.merge_range('O4:P4', '%s' % date_start.strftime(format_new), formats['date'])
            sheet.merge_range('Q4:R4', 'Hasta', formats['string'])
            sheet.merge_range('S4:T4', '%s' % date_end.strftime(format_new), formats['date'])

            sheet.set_row(5, 30)
            sheet.merge_range('N6:Z6', 'Compras Internas', formats['title'])
            sheet.merge_range('AA6:AB6', 'Compras de Importaciones', formats['title'])
            sheet.merge_range('AC6:AD6', 'Retención IVA Proveedores', formats['title'])

            row = 6
            col = 1
            titles = [(1, 'Nro. Op'), (2, 'Fecha Emisión Doc.'), (3, 'Nro. de RIF'), (4, 'Nombre ó Razón Social'),
                      (5, 'Tipo Prov.'),
                      (6, 'Nro. de Factura'), 
                      (7, 'Nro. Nota de Crédito'),
                      (8, 'Nro. Nota de Débito'),
                      (9, 'Nro. de Control'), 
                      (10, 'Tipo de Trans'), (11, 'Nro. Factura Afectada'), (12, 'Total Compras con IVA'),
                      (13, 'Compras sin Derecho a Crédito'),
                      (14, 'Base Imponible Alicuota General'),
                      (15, '% Alicuota General'),
                      (16, 'Impuesto (I.V.A) Alicuota General'),
                      (17, 'Base Imponible Alicuota General No Deducible'),
                      (18, '% Alicuota General No Deducible'),
                      (19, 'Impuesto (I.V.A) Alicuota General No Deducible'),
                      (20, 'Base Imponible Alicuota Reducida'),
                      (21, '% Alicuota Reducida'),
                      (22, 'Impuesto (I.V.A) Alicuota Reducida'),
                      (23, 'Base Imponible Alicuota Adicional'),
                      (24, '% Alicuota Adicional'),
                      (25, 'Impuesto (I.V.A) Alicuota Adicional'),
                      (26, 'Base Imponible Alicuota General'),
                      (27, '% Alicuota General'),
                      (28, 'Impuesto (I.V.A) Alicuota General'),
                      (29, 'Nro. Planilla Importación'),
                      (30, 'Nro. Expediente Importación'),
                      (31, 'Nro. de Comprobante'),
                      (32, 'IVA Ret (Vend.)')]

            # sheet.set_row(6, cell_format=formats['title'])
            for title in titles:
                format_t = formats['title']
                if col in [14,15,16]:
                    format_t = formats['title2']
                if col in [17,18,19]:
                    format_t = formats['title3']
                if col in [20, 21, 22]:
                    format_t = formats['title4']
                sheet.write(row, col, title[1], format_t)
                col += 1
            row += 1
            col = 1

            contador_datos_compras = 1
            row_suma_ini = row
            for d in datos_compras:
                col = 1
                sheet.write(row, col, contador_datos_compras)
                col += 1
                sheet.write(row, col, d['emission_date'])
                col += 1
                sheet.write(row, col, self.remove_hyphens(d['partner_vat']))
                col += 1
                sheet.write(row, col, d['partner_name'])
                col += 1
                sheet.write(row, col, d['people_type'])
                col += 1
                sheet.write(row, col, d['invoice_number'] if d['invoice_number'] and d['doc_type'] == 'FACT' else '', formats['string'])
                col += 1
                sheet.write(row, col, d['credit_affected'] if d['doc_type'] == 'N/CR' else '', formats['string'])
                col += 1
                sheet.write(row, col, d['debit_affected'] if d['debit_affected'] else '', formats['string'])
                col += 1
                sheet.write(row, col, d['ctrl_number'], formats['string'])
                col += 1
                sheet.write(row, col, d['type'])
                col += 1
                sheet.write(row, col, d['affected_invoice'] if d['affected_invoice'] else '', formats['string'])
                col += 1
                sheet.write(row, col, d['total_with_iva'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_exempt'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_general_base'] if not d['no_deducible'] and not d['nro_expediente_impor'] else 0, formats['number'])
                col += 1
                sheet.write(row, col, d['vat_general_rate'] if not d['no_deducible'] and not d['nro_expediente_impor'] else 0, formats['number'])
                col += 1
                #print(d['invoice_id'],d['invoice_id'].no_deducible)
                sheet.write(row, col, d['vat_general_tax'] if not d['no_deducible'] and not d['nro_expediente_impor'] else 0, formats['number'])
                col += 1
                sheet.write(row, col, d['vat_general_base'] if d['no_deducible'] and not d['nro_expediente_impor'] else 0,formats['number'])  # R
                col += 1
                sheet.write(row, col, d['vat_general_rate'] if d['no_deducible'] and not d['nro_expediente_impor'] else 0, formats['number'])
                col += 1
                sheet.write(row, col, d['vat_general_tax'] if d['no_deducible'] and not d['nro_expediente_impor'] else 0, formats['number']) #R
                col += 1
                sheet.write(row, col, d['vat_reduced_base'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_reduced_rate'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_reduced_tax'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_additional_base'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_additional_rate'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_additional_tax'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_general_base_importaciones'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_general_rate_importaciones'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_general_tax_importaciones'], formats['number'])
                col += 1
                sheet.write(row, col, d['nro_planilla'], formats['string'])
                col += 1
                sheet.write(row, col, d['nro_expediente'], formats['string'])
                col += 1
                sheet.write(row, col, str(d['wh_number']), formats['number_sd'])
                col += 1
                sheet.write(row, col, d['get_wh_vat'], formats['number'])

                row += 1
                contador_datos_compras += 1
            row_suma_fin = row
            # imprimir totales y resumen
            row += 1
            col = 11
            row_totales = row + 1
            sheet.write(row, col, 'TOTALES', formats['title'])
            col = 12
            sheet.write(row, col, '=SUM(M%s:M%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 13
            sheet.write(row, col, '=SUM(N%s:N%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 14
            sheet.write(row, col, '=SUM(O%s:O%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 15
            sheet.write(row, col, '', formats['title_number'])
            col = 16
            sheet.write(row, col, '=SUM(Q%s:Q%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 17
            sheet.write(row, col, '=SUM(R%s:R%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 18
            sheet.write(row, col, '', formats['title_number']) #S
            col = 19
            sheet.write(row, col, '=SUM(T%s:T%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 20
            sheet.write(row, col, '=SUM(U%s:U%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 21
            sheet.write(row, col, '', formats['title_number']) #S
            col = 22
            sheet.write(row, col, '=SUM(W%s:W%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 23
            sheet.write(row, col, '=SUM(X%s:X%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 24
            sheet.write(row, col, '', formats['title_number'])
            col = 25
            sheet.write(row, col, '=SUM(Z%s:Z%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 26
            sheet.write(row, col, '=SUM(AA%s:AA%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 27

            sheet.write(row, col, '', formats['title_number'])
            col = 28
            sheet.write(row, col, '=SUM(AC%s:AC%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 29
            sheet.write(row, col, '', formats['title_number'])
            col = 30
            sheet.write(row, col, '', formats['title_number'])
            col = 31
            sheet.write(row, col, '', formats['title_number'])
            col = 32
            sheet.write(row, col, '=SUM(AG%s:AG%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])

            # resumen
            row += 4
            sheet.set_row(row - 1, 25)
            sheet.merge_range('L%s:T%s' % (row, row), 'Resumen de Libro de Compras', formats['title'])
            sheet.merge_range('U%s:Y%s' % (row, row), 'Base Imponible', formats['title'])
            sheet.merge_range('Z%s:AC%s' % (row, row), 'Crédito Fiscal', formats['title'])
            row += 1
            row_resumen = row
            sheet.merge_range('L%s:T%s' % (row, row), 'Compras Internas no Gravadas y/o Sin Derecho a Crédito Fiscal')
            sheet.merge_range('U%s:Y%s' % (row, row), '=SUM(N%s,R%s)' % (row_totales, row_totales), formats['number'])
            sheet.merge_range('Z%s:AC%s' % (row, row), '=T%s' % row_totales, formats['number'])
            row += 1
            sheet.merge_range('L%s:T%s' % (row, row), 'Compras Internas gravadas por Alicuota General ')
            sheet.merge_range('U%s:Y%s' % (row, row), '=O%s' % row_totales, formats['number'])
            sheet.merge_range('Z%s:AC%s' % (row, row), '=Q%s' % row_totales, formats['number'])
            row += 1
            sheet.merge_range('L%s:T%s' % (row, row),
                              'Compras Internas gravadas por Alicuota General mas Alicuota Adicional ')
            sheet.merge_range('U%s:Y%s' % (row, row), '=X%s' % row_totales, formats['number'])
            sheet.merge_range('Z%s:AC%s' % (row, row), '=Z%s' % row_totales, formats['number'])
            row += 1
            sheet.merge_range('L%s:T%s' % (row, row),
                              'Compras Internas gravadas por Alicuota Reducida')
            sheet.merge_range('U%s:Y%s' % (row, row), '=U%s' % row_totales, formats['number'])
            sheet.merge_range('Z%s:AC%s' % (row, row), '=W%s' % row_totales, formats['number'])
            row += 1
            sheet.merge_range('L%s:T%s' % (row, row),
                              'Importaciones gravadas Alícuota General ')
            sheet.merge_range('U%s:Y%s' % (row, row), '=AA%s' % row_totales, formats['number'])
            sheet.merge_range('Z%s:AC%s' % (row, row), '=AC%s' % row_totales, formats['number'])
            row += 1
            sheet.merge_range('L%s:T%s' % (row, row),
                              'Importaciones gravadas por Alícuota General mas Adicional ')
            sheet.merge_range('U%s:Y%s' % (row, row), '=X%s', formats['number'])
            sheet.merge_range('Z%s:AC%s' % (row, row), '=Z%s', formats['number'])
            row += 1
            sheet.merge_range('L%s:T%s' % (row, row),
                              'Importaciones gravadas por Alicuota Reducida')
            sheet.merge_range('U%s:Y%s' % (row, row), 0.0, formats['number'])
            sheet.merge_range('Z%s:AC%s' % (row, row), 0.0, formats['number'])
            row += 1
            sheet.merge_range('L%s:T%s' % (row, row),
                              'Total Compras y Créditos Fiscales ',
                              formats['title'])
            sheet.merge_range('U%s:Y%s' % (row, row), '=SUM(U%s:Y%s)' % (row_resumen, row - 1), formats['title_number'])
            sheet.merge_range('Z%s:AC%s' % (row, row), '=SUM(Z%s:AC%s)' % (row_resumen, row - 1), formats['title_number'])
            row += 1
            sheet.merge_range('L%s:T%s' % (row, row),
                              'Total IVA Retenido',
                              formats['title'])
            sheet.merge_range('U%s:Y%s' % (row, row), '', formats['title_number'])
            sheet.merge_range('Z%s:AC%s' % (row, row), '=AG%s' % row_totales, formats['title_number'])

            row += 3
            col = 1

            if datos_compras_ajustes:
                sheet.merge_range('B%s:G%s' % (row, row), 'AJUSTE A CREDITOS FISCALES PERIODOS ANTERIORES')
                row += 1

                for title in titles:
                    sheet.write(row, col, title[1], formats['title'])
                    col += 1
                row += 1
                col = 1

                contador_datos_compras_ajustes = 1
                row_suma_ini_ajustes = row
                for d in datos_compras_ajustes:
                    col = 1
                    sheet.write(row, col, contador_datos_compras_ajustes)
                    col += 1
                    sheet.write(row, col, d['emission_date'])
                    col += 1
                    sheet.write(row, col, self.remove_hyphens(d['partner_vat']))
                    col += 1
                    sheet.write(row, col, d['partner_name'])
                    col += 1
                    sheet.write(row, col, d['people_type'])
                    col += 1
                    sheet.write(row, col, d['invoice_number'] if d['invoice_number'] and d['doc_type'] == 'FACT' else '', formats['string'])
                    col += 1
                    sheet.write(row, col, d['credit_affected'] if d['doc_type'] == 'N/CR' else '', formats['string'])
                    col += 1
                    sheet.write(row, col, d['debit_affected'] if d['debit_affected'] else '', formats['string'])
                    col += 1
                    sheet.write(row, col, d['ctrl_number'], formats['string'])
                    col += 1
                    sheet.write(row, col, d['type'])
                    col += 1
                    sheet.write(row, col, d['affected_invoice'] if d['affected_invoice'] else '', formats['string'])
                    col += 1
                    sheet.write(row, col, d['total_with_iva'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_exempt'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_general_base'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_general_rate'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_general_tax'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_reduced_base'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_reduced_rate'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_reduced_tax'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_additional_base'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_additional_rate'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_additional_tax'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_general_base_importaciones'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_general_rate_importaciones'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_general_tax_importaciones'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['nro_planilla'], formats['string'])
                    col += 1
                    sheet.write(row, col, d['nro_expediente'], formats['string'])
                    col += 1
                    sheet.write(row, col, str(d['wh_number']), formats['number_sd'])
                    col += 1
                    sheet.write(row, col, d['get_wh_vat'], formats['number'])

                    row += 1
                    contador_datos_compras_ajustes += 1
                row_suma_fin_ajustes = row
                # imprimir totales y resumen en ajustes
                row += 1
                col = 11
                sheet.write(row, col, 'TOTALES', formats['title'])
                col = 12
                sheet.write(row, col, '=SUM(M%s:M%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes),
                            formats['title_number'])
                col = 13
                sheet.write(row, col, '=SUM(N%s:N%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes),
                            formats['title_number'])
                col = 14
                sheet.write(row, col, '=SUM(O%s:O%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes),
                            formats['title_number'])
                col = 15
                sheet.write(row, col, '', formats['title_number'])
                col = 16
                sheet.write(row, col, '=SUM(Q%s:Q%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes),
                            formats['title_number'])
                col = 17
                sheet.write(row, col, '=SUM(R%s:R%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes),
                            formats['title_number'])
                col = 18
                sheet.write(row, col, '', formats['title_number'])
                col = 19
                sheet.write(row, col, '=SUM(U%s:U%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes),
                            formats['title_number'])
                col = 20
                sheet.write(row, col, '=SUM(V%s:V%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes),
                            formats['title_number'])
                col = 21
                sheet.write(row, col, '', formats['title_number'])
                col = 22
                sheet.write(row, col, '=SUM(X%s:X%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes),
                            formats['title_number'])
                col = 23
                sheet.write(row, col, '=SUM(Y%s:Y%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes),
                            formats['title_number'])
                col = 24
                sheet.write(row, col, '', formats['title_number'])
                col = 25
                sheet.write(row, col, '=SUM(AA%s:AA%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes),
                            formats['title_number'])
                col = 26
                sheet.write(row, col, '', formats['title_number'])
                col = 27
                sheet.write(row, col, '', formats['title_number'])
                col = 28
                sheet.write(row, col, '', formats['title_number'])
                col = 29
                sheet.write(row, col, '=SUM(AE%s:AE%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes),
                            formats['title_number'])

            sheet.set_column('EA:EA', 15)

            workbook.close()
            # with open(file_name, "rb") as file:
            #     file_base64 = base64.b64encode(file.read())
            file_base64 = base64.b64encode(output.getvalue())

            file_name = 'Libro de Compra'
            attachment_id = self.env['ir.attachment'].sudo().create({
                'name': file_name,
                'datas': file_base64
            })
            action = {
                'type': 'ir.actions.act_url',
                'url': '/web/content/{}?download=true'.format(attachment_id.id, ),
                'target': 'current',
            }
            return action
        else:
            ##excel de ventas
            file_name = 'Libro_Venta.xlsx'
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True, 'strings_to_numbers': True})
            sheet = workbook.add_worksheet('Libro de Venta')
            formats = self.set_formats(workbook)
            formatos = self.set_formatos(workbook)
            datos_ventas, datos_ventas_ajustes = self.get_datas_ventas()
            if not datos_ventas:
                raise UserError('No hay datos disponibles')
            sheet.merge_range('B3:G3', datos_ventas[0]['company_name'], formats['string_titulo'])
            sheet.merge_range('M3:T3', 'Libro de Venta', formats['string_titulo'])
            sheet.merge_range('B4:G4', datos_ventas[0]['company_rif'], formats['string'])
            format_new = "%d/%m/%Y"
            date_start = datetime.strptime(str(self.date_start), DATE_FORMAT).date()
            date_end = datetime.strptime(str(self.date_end), DATE_FORMAT).date()

            sheet.merge_range('M4:N4', 'Desde', formats['string'])
            sheet.merge_range('O4:P4', '%s' % date_start.strftime(format_new), formats['date'])
            sheet.merge_range('Q4:R4', 'Hasta', formats['string'])
            sheet.merge_range('S4:T4', '%s' % date_end.strftime(format_new), formats['date'])

            sheet.merge_range('Q6:Y6', 'Ventas Internas ó Exportación Gravadas', formats['title'])

            row = 6
            col = 1
            titles = [(1, 'Nro. Op'), (2, 'Nro. Reporte Z'), (3, 'Fecha Documento'), (4, 'RIF'),
                      (5, 'Nombre ó Razón Social'),
                      (6, 'Tipo Prov.'), 
                      (7, 'Tipo de Trans.'),
                      (8, 'Tipo de Documento'),
                      (9, 'Nro. De Factura'),
                      (10, 'Nro. Nota de Crédito'),
                      (11, 'Nro. Nota de Débito'),
                      (12, 'Nro. De Control'),
                      (13, 'Nro. Ultima Factura'), 
                      (14, 'Nro. Factura Afectada'),
                      (15, 'Nro. Planilla de Exportación'),
                      (16, 'Ventas Incluyendo IVA'), 
                      (17, 'Ventas Internas ó Exportaciones No Gravadas'),
                      (18, 'Ventas Internas ó Exportaciones Exoneradas'),
                      (19, 'Base Imponible Alicuota General'), 
                      (20, '% Alícuota General'),
                      (21, 'Impuesto IVA Alicuota General'),
                      (22, 'Base Imponible Alicuota Reducida'), 
                      (23, '% Alícuota Reducida'),
                      (24, 'Impuesto IVA Alicuota Reducida'),
                      (25, 'Base Imponible Alicuota Adicional'), 
                      (26, '% Alícuota Adicional'),
                      (27, 'Impuesto IVA Alicuota Adicional'),
                      (28, 'IVA Retenido (Comprador)'),
                      (29, 'Nro. De Comprobante'), 
                      (30, 'Fecha Comp.')]

            # sheet.set_row(6, cell_format=formats['title'])
            for title in titles:
                sheet.write(row, col, title[1], formats['title'])
                col += 1
            row += 1
            col = 1
            contador_datos_ventas = 1
            row_suma_ini = row
            for d in datos_ventas:
                col = 1
                sheet.write(row, col, contador_datos_ventas)
                col += 1
                sheet.write(row, col, d['report_z'] if d['report_z'] else '')
                col += 1
                sheet.write(row, col, d['emission_date'])
                col += 1
                sheet.write(row, col, self.remove_hyphens(d['partner_vat']))
                col += 1
                sheet.write(row, col, d['partner_name'])
                col += 1
                sheet.write(row, col, d['people_type'])
                col += 1
                sheet.write(row, col, d['type'])
                col += 1
                sheet.write(row, col, 'NC' if d['doc_type'] == 'N/CR' else 'ND' if d['doc_type'] == 'N/DB' else 'FAC' if d['doc_type'] == 'FACT' else '')
                col += 1
                sheet.write_string(row, col, str(d['invoice_number']) if d['invoice_number'] and d['doc_type'] == 'FACT' else '', formatos['text'])
                col += 1
                sheet.write_string(row, col, str(d['credit_note']) if d['credit_note'] else '', formatos['text'])
                col += 1
                sheet.write_string(row, col, str(d['debit_note']) if d['debit_note'] else '', formatos['text'])
                col += 1
                sheet.write(row, col, str(d['ctrl_number']) if d['ctrl_number'] else '', formatos['text'])
                col += 1
                sheet.write_string(row, col, str(d['n_ultima_factZ']) if d['n_ultima_factZ'] else '', formatos['text'])
                col += 1
                sheet.write_string(row, col, str(d['affected_invoice']) if d['affected_invoice'] else '', formatos['text'])
                col += 1
                sheet.write(row, col, d['export_form'])
                col += 1
                sheet.write(row, col, d['total_w_iva'], formats['number'])
                col += 1
                sheet.write(row, col, d['no_taxe_sale'], formats['number'])
                col += 1
                sheet.write(row, col, d['export_sale'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_general_base'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_general_rate'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_general_tax'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_reduced_base'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_reduced_rate'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_reduced_tax'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_additional_base'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_additional_rate'], formats['number'])
                col += 1
                sheet.write(row, col, d['vat_additional_tax'], formats['number'])
                col += 1
                sheet.write(row, col, d['get_wh_vat'], formats['number'])
                col += 1
                sheet.write(row, col, d['wh_number'] if d['wh_number'] else '')
                col += 1
                sheet.write(row, col, '%s' % d['date_wh_number'].strftime(format_new) if d['date_wh_number'] else '', formats['date'] if d['date_wh_number'] else '')

                row += 1
                contador_datos_ventas += 1

            row_suma_fin = row
            # imprimir totales y resumen
            row += 1
            col = 15
            row_totales = row + 1
            sheet.write(row, col, 'TOTALES', formats['title'])
            col = 16
            sheet.write(row, col, '=SUM(Q%s:Q%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 17
            sheet.write(row, col, '=SUM(R%s:R%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 18
            sheet.write(row, col, '=SUM(S%s:S%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 19
            sheet.write(row, col, '=SUM(T%s:T%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 20
            sheet.write(row, col, '', formats['title_number'])
            col = 21
            sheet.write(row, col, '=SUM(V%s:V%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 22
            sheet.write(row, col, '=SUM(W%s:W%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 23
            sheet.write(row, col, '', formats['title_number'])
            col = 24
            sheet.write(row, col, '=SUM(Y%s:Y%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 25
            sheet.write(row, col, '=SUM(Z%s:Z%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 26
            sheet.write(row, col, '', formats['title_number'])
            col = 27
            sheet.write(row, col, '=SUM(AB%s:AB%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 28
            sheet.write(row, col, '=SUM(AC%s:AC%s)' % (row_suma_ini, row_suma_fin), formats['title_number'])
            col = 29
            sheet.write(row, col, '', formats['title_number'])
            col = 30
            sheet.write(row, col, '', formats['title_number'])

            # resumen
            row += 4

            sheet.merge_range('L%s:R%s' % (row, row), 'Resumen de Libro de Ventas', formats['title'])
            sheet.merge_range('S%s:U%s' % (row, row), 'Base Imponible', formats['title'])
            sheet.merge_range('V%s:X%s' % (row, row), 'Débito Fiscal', formats['title'])
            sheet.merge_range('Y%s:AA%s' % (row, row), 'IVA Retenido por el Comprador', formats['title'])
            row += 1
            row_resumen = row
            sheet.merge_range('L%s:R%s' % (row, row), 'Ventas Internas Exoneradas')
            sheet.merge_range('S%s:U%s' % (row, row), '=R%s' % row_totales, formats['number'])
            sheet.merge_range('V%s:X%s' % (row, row), 0.0, formats['number'])
            sheet.merge_range('Y%s:AA%s' % (row, row), 0.0, formats['number'])
            row += 1
            sheet.merge_range('L%s:R%s' % (row, row), 'Ventas de Exportación')
            sheet.merge_range('S%s:U%s' % (row, row), 0.0, formats['number'])
            sheet.merge_range('V%s:X%s' % (row, row), 0.0, formats['number'])
            sheet.merge_range('Y%s:AA%s' % (row, row), 0.0, formats['number'])
            row += 1
            sheet.merge_range('L%s:R%s' % (row, row), 'Ventas Internas gravadas por Alicuota General')
            sheet.merge_range('S%s:U%s' % (row, row), '=T%s' % row_totales, formats['number'])
            sheet.merge_range('V%s:X%s' % (row, row), '=V%s' % row_totales, formats['number'])
            sheet.merge_range('Y%s:AA%s' % (row, row), '=AC%s' % row_totales, formats['number'])
            row += 1
            sheet.merge_range('L%s:R%s' % (row, row),
                              'Ventas Internas gravadas por Alicuota General mas Alicuota Adicional ')
            sheet.merge_range('S%s:U%s' % (row, row), '=AB%s' % row_totales, formats['number'])
            sheet.merge_range('V%s:X%s' % (row, row), '=AA%s' % row_totales, formats['number'])
            sheet.merge_range('Y%s:AA%s' % (row, row), 0.0, formats['number'])
            row += 1
            sheet.merge_range('L%s:R%s' % (row, row), 'Ventas Internas gravadas por Alicuota Reducida')
            sheet.merge_range('S%s:U%s' % (row, row), '=Y%s' % row_totales, formats['number'])
            sheet.merge_range('V%s:X%s' % (row, row), '=W%s' % row_totales, formats['number'])
            sheet.merge_range('Y%s:AA%s' % (row, row), 0.0, formats['number'])
            row += 1
            sheet.merge_range('L%s:R%s' % (row, row), 'Total Ventas y Debitos Fiscales', formats['title'])
            sheet.merge_range('S%s:U%s' % (row, row), '=SUMA(S%s:U%s)' % (row_resumen, row - 1),
                              formats['title_number'])
            sheet.merge_range('V%s:X%s' % (row, row), '=SUMA(V%s:X%s)' % (row_resumen, row - 1),
                              formats['title_number'])
            sheet.merge_range('Y%s:AA%s' % (row, row), '=SUMA(Y%s:AA%s)' % (row_resumen, row - 1),
                              formats['title_number'])
            row += 1
            if datos_ventas_ajustes:
                row += 3
                col = 1
                sheet.merge_range('B%s:G%s' % (row, row), 'RETENCIONES DE PERIODOS ANTERIORES')
                row += 1
                for title in titles:
                    sheet.write(row, col, title[1], formats['title'])
                    col += 1
                row += 1
                col = 1
                contador_datos_ventas_ajustes = 1
                row_suma_ini_ajustes = row
                for d in datos_ventas_ajustes:
                    col = 1
                    sheet.write(row, col, contador_datos_ventas_ajustes)
                    col += 1
                    sheet.write(row, col, d['report_z'] if d['report_z'] else '')
                    col += 1
                    sheet.write(row, col, d['emission_date'])
                    col += 1
                    sheet.write(row, col, self.remove_hyphens(d['partner_vat']))
                    col += 1
                    sheet.write(row, col, d['partner_name'])
                    col += 1
                    sheet.write(row, col, d['people_type'])
                    col += 1
                    sheet.write(row, col, d['type'])
                    col += 1
                    sheet.write(row, col, 'NC' if d['doc_type'] == 'N/CR' else 'ND' if d['doc_type'] == 'N/DB' else 'FAC' if d['doc_type'] == 'FACT' else '')
                    col += 1
                    sheet.write_string(row, col, str(d['invoice_number']) if d['invoice_number'] and d['doc_type'] == 'FACT' else '', formatos['text'])
                    col += 1
                    sheet.write_string(row, col, str(d['credit_note']) if d['credit_note'] else '', formatos['text'])
                    col += 1
                    sheet.write_string(row, col, str(d['debit_note']) if d['debit_note'] else '', formatos['text'])
                    col += 1
                    sheet.write(row, col, str(d['ctrl_number']) if d['ctrl_number'] else '', formatos['text'])
                    col += 1
                    sheet.write_string(row, col, str(d['n_ultima_factZ']) if d['n_ultima_factZ'] else '', formatos['text'])
                    col += 1
                    sheet.write_string(row, col, str(d['affected_invoice']) if d['affected_invoice'] else '', formatos['text'])
                    col += 1
                    sheet.write(row, col, d['export_form'])
                    col += 1
                    sheet.write(row, col, d['total_w_iva'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['no_taxe_sale'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['export_sale'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_general_base'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_general_rate'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_general_tax'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_reduced_base'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_reduced_rate'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_reduced_tax'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_additional_base'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_additional_rate'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['vat_additional_tax'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['get_wh_vat'], formats['number'])
                    col += 1
                    sheet.write(row, col, d['wh_number'] if d['wh_number'] else '')
                    col += 1
                    sheet.write(row, col, '%s' % d['date_wh_number'].strftime(format_new) if d['date_wh_number'] else '', formats['date'] if d['date_wh_number'] else '')

                    row += 1
                    contador_datos_ventas_ajustes += 1

                row_suma_fin_ajustes = row
                # imprimir totales y resumen
                row += 1
                col = 15
                row_totales = row + 1
                sheet.write(row, col, 'TOTALES', formats['title'])
                col = 16
                sheet.write(row, col, '=SUM(Q%s:Q%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes), formats['title_number'])
                col = 17
                sheet.write(row, col, '=SUM(R%s:R%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes), formats['title_number'])
                col = 18
                sheet.write(row, col, '=SUM(S%s:S%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes), formats['title_number'])
                col = 19
                sheet.write(row, col, '=SUM(T%s:T%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes), formats['title_number'])
                col = 20
                sheet.write(row, col, '', formats['title_number'])
                col = 21
                sheet.write(row, col, '=SUM(V%s:V%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes), formats['title_number'])
                col = 22
                sheet.write(row, col, '=SUM(W%s:W%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes), formats['title_number'])
                col = 23
                sheet.write(row, col, '', formats['title_number'])
                col = 24
                sheet.write(row, col, '=SUM(Y%s:Y%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes), formats['title_number'])
                col = 25
                sheet.write(row, col, '=SUM(Z%s:Z%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes), formats['title_number'])
                col = 26
                sheet.write(row, col, '', formats['title_number'])
                col = 27
                sheet.write(row, col, '=SUM(AB%s:AB%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes), formats['title_number'])
                col = 28
                sheet.write(row, col, '=SUM(AC%s:AC%s)' % (row_suma_ini_ajustes, row_suma_fin_ajustes), formats['title_number'])
                col = 29
                sheet.write(row, col, '', formats['title_number'])
                col = 30
                sheet.write(row, col, '', formats['title_number'])


            workbook.close()
            # with open(file_name, "rb") as file:
            #     file_base64 = base64.b64encode(file.read())
            file_base64 = base64.b64encode(output.getvalue())
            file_name = 'Libro de Venta'
            attachment_id = self.env['ir.attachment'].sudo().create({
                'name': file_name,
                'datas': file_base64
            })
            action = {
                'type': 'ir.actions.act_url',
                'url': '/web/content/{}?download=true'.format(attachment_id.id, ),
                'target': 'current',
            }
            return action

    def get_datas_compras(self):
        datos_compras = []
        datos_compras_ajustes = []
        for rec in self:
            format_new = "%d/%m/%Y"
            date_start = datetime.strptime(str(self.date_start), DATE_FORMAT)
            date_end = datetime.strptime(str(self.date_end), DATE_FORMAT)

            purchasebook_ids = self.env['account.fiscal.book.line'].search(
                [('fb_id', '=', self.env.context['active_id']),
                 ('accounting_date', '>=', date_start.strftime(DATETIME_FORMAT)),
                 ('accounting_date', '<=', date_end.strftime(DATETIME_FORMAT))], order='rank asc')

            emission_date = ' '
            sum_compras_credit = 0
            sum_total_with_iva = 0
            sum_vat_general_base = 0
            sum_vat_general_tax = 0
            sum_vat_reduced_base = 0
            sum_vat_reduced_tax = 0
            sum_vat_additional_base = 0
            sum_vat_additional_tax = 0
            sum_get_wh_vat = 0
            suma_vat_exempt = 0

            sum_compras_credit_ajustes = 0
            sum_total_with_iva_ajustes = 0
            sum_vat_general_base_ajustes = 0
            sum_vat_general_tax_ajustes = 0
            sum_vat_reduced_base_ajustes = 0
            sum_vat_reduced_tax_ajustes = 0
            sum_vat_additional_base_ajustes = 0
            sum_vat_additional_tax_ajustes = 0
            sum_get_wh_vat_ajustes = 0
            suma_vat_exempt_ajustes = 0

            vat_reduced_base = 0
            vat_reduced_rate = 0
            vat_reduced_tax = 0
            vat_additional_base = 0
            vat_additional_rate = 0
            vat_additional_tax = 0

            ''' COMPRAS DE IMPORTACIONES'''

            sum_total_with_iva_importaciones = 0
            sum_vat_general_base_importaciones = 0
            suma_base_general_importaciones = 0
            sum_base_general_tax_importaciones = 0
            sum_vat_general_tax_importaciones = 0
            sum_vat_reduced_base_importaciones = 0
            sum_vat_reduced_tax_importaciones = 0
            sum_vat_additional_base_importaciones = 0
            sum_vat_additional_tax_importaciones = 0

            hola = 0
            #######################################
            compras_credit = 0
            origin = 0
            number = 0

            for h in purchasebook_ids:
                h_vat_general_base = 0.0
                h_vat_general_rate = 0.0
                h_vat_general_tax = 0.0
                vat_general_base_importaciones = 0
                vat_general_rate_importaciones = 0
                vat_general_general_rate_importaciones = 0
                vat_general_tax_importaciones = 0
                vat_reduced_base_importaciones = 0
                vat_reduced_rate_importaciones = 0
                vat_reduced_tax_importaciones = 0
                vat_additional_tax_importaciones = 0
                vat_additional_rate_importaciones = 0
                vat_additional_base_importaciones = 0
                vat_reduced_base = 0
                vat_reduced_rate = 0
                vat_reduced_tax = 0
                vat_additional_base = 0
                vat_additional_rate = 0
                vat_additional_tax = 0
                get_wh_vat = 0

                if h.type == 'ntp':
                    compras_credit = h.invoice_id.amount_untaxed

                if h.doc_type == 'N/DB':
                    origin = h.affected_invoice
                    if h.invoice_id:
                        if h.invoice_id.nro_ctrl:
                            busq1 = self.env['account.move'].search([('nro_ctrl', '=', h.invoice_id.nro_ctrl)])
                            if busq1:
                                for busq2 in busq1:
                                    if busq2.move_type == 'in_invoice':
                                        number = busq2.name or ''

                sum_compras_credit += compras_credit
                suma_vat_exempt += h.vat_exempt
                planilla = ''
                expediente = ''
                total = 0
                partner = self.env['res.partner'].search([('rif', '=', h.partner_vat)])
                if partner and len(partner) == 1:
                    partner_1 = partner
                else:
                    partner = self.env['res.partner'].search([('name', '=', h.partner_vat)])
                    partner_1 = partner
                if h.invoice_id:
                    partner = h.invoice_id.partner_id
                    partner_1 = partner
                if (partner_1.company_type == 'company' or partner_1.company_type == 'person') and (
                        partner_1.people_type_company or partner_1.people_type_individual) and (
                        partner_1.people_type_company == 'pjdo' or partner_1.people_type_individual == 'pnre' or partner_1.people_type_individual == 'pnnr'):
                    '####################### NO ES PROVEDOR INTERNACIONAL########################################################3'

                    if h.invoice_id:
                        tasa = 1
                        if h.invoice_id.currency_id.name == "USD":
                            tasa = self.obtener_tasa(h.invoice_id)
                        if h.doc_type == 'N/CR':
                            total = (h.invoice_id.amount_total) * -1 * tasa
                        else:
                            total = (h.invoice_id.amount_total) * tasa
                        sum_vat_reduced_base += h.vat_reduced_base  # Base Imponible de alicuota Reducida
                        sum_vat_reduced_tax += h.vat_reduced_tax  # Impuesto de IVA alicuota reducida
                        sum_vat_additional_base += h.vat_additional_base  # BASE IMPONIBLE ALICUOTA ADICIONAL

                        sum_vat_additional_tax += h.vat_additional_tax  # IMPUESTO DE IVA ALICUOTA ADICIONAL

                        sum_total_with_iva = (
                                h.fb_id.base_amount + h.fb_id.tax_amount) if h.emission_date >= date_start.date() else 0  # Total monto con IVA
                        sum_total_with_iva_ajustes = (
                                h.fb_id.base_amount + h.fb_id.tax_amount) if h.emission_date < date_start.date() else 0
                        # Total monto con IVA
                        sum_vat_general_base += h.vat_general_base  # Base Imponible Alicuota general
                        sum_vat_general_tax += h.vat_general_tax  # Impuesto de IVA
                        h_vat_general_base = h.vat_general_base
                        h_vat_general_rate = (
                                h.vat_general_base and h.vat_general_tax * 100 / h.vat_general_base) if h.vat_general_base else 0.0
                        h_vat_general_rate = round(h_vat_general_rate, 0)
                        h_vat_general_tax = h.vat_general_tax if h.vat_general_tax else 0.0
                        vat_reduced_base = h.vat_reduced_base
                        vat_reduced_rate = int(h.vat_reduced_base and h.vat_reduced_tax * 100 / h.vat_reduced_base)
                        vat_reduced_tax = h.vat_reduced_tax
                        vat_additional_base = h.vat_additional_base
                        vat_additional_rate = int(
                            h.vat_additional_base and h.vat_additional_tax * 100 / h.vat_additional_base)
                        vat_additional_tax = h.vat_additional_tax
                        get_wh_vat = h.get_wh_vat

                        emission_date = datetime.strftime(
                            datetime.strptime(str(h.emission_date), DEFAULT_SERVER_DATE_FORMAT),
                            format_new)
                    if h.iwdl_id.invoice_id:

                        tasa = 1
                        if h.iwdl_id.invoice_id.currency_id.name == "USD":
                            tasa = self.obtener_tasa(h.iwdl_id.invoice_id)
                        if h.doc_type == 'N/CR':
                            total = (h.iwdl_id.invoice_id.amount_total) * -1 * tasa
                        else:
                            total = (h.iwdl_id.invoice_id.amount_total) * tasa
                        sum_vat_reduced_base += h.vat_reduced_base  # Base Imponible de alicuota Reducida
                        sum_vat_reduced_tax += h.vat_reduced_tax
                        # Impuesto de IVA alicuota reducida

                        sum_vat_additional_base += h.vat_additional_base  # BASE IMPONIBLE ALICUOTA ADICIONAL

                        sum_vat_additional_tax += h.vat_additional_tax  # IMPUESTO DE IVA ALICUOTA ADICIONAL

                        sum_total_with_iva = (
                                h.fb_id.base_amount + h.fb_id.tax_amount) if h.emission_date >= date_start.date() else 0  # Total monto con IVA
                        sum_total_with_iva_ajustes = (
                                h.fb_id.base_amount + h.fb_id.tax_amount) if h.emission_date < date_start.date() else 0
                        sum_vat_general_base += h.vat_general_base  # Base Imponible Alicuota general
                        sum_vat_general_tax += h.vat_general_tax  # Impuesto de IVA
                        h_vat_general_base = h.vat_general_base
                        h_vat_general_rate = (
                                h.vat_general_base and h.vat_general_tax * 100 / h.vat_general_base) if h.vat_general_base else 0.0
                        h_vat_general_rate = round(h_vat_general_rate, 0)
                        h_vat_general_tax = h.vat_general_tax if h.vat_general_tax else 0.0
                        vat_reduced_base = h.vat_reduced_base
                        vat_reduced_rate = int(h.vat_reduced_base and h.vat_reduced_tax * 100 / h.vat_reduced_base)
                        vat_reduced_tax = h.vat_reduced_tax
                        vat_additional_base = h.vat_additional_base
                        vat_additional_rate = int(
                            h.vat_additional_base and h.vat_additional_tax * 100 / h.vat_additional_base)
                        vat_additional_tax = h.vat_additional_tax
                        get_wh_vat = h.get_wh_vat

                        emission_date = datetime.strftime(
                            datetime.strptime(str(h.emission_date), DEFAULT_SERVER_DATE_FORMAT),
                            format_new)

                if (partner_1.company_type == 'company' or partner_1.company_type == 'person') and (
                        partner_1.people_type_company or partner_1.people_type_individual) and partner_1.people_type_company == 'pjnd':
                    '############## ES UN PROVEEDOR INTERNACIONAL ##############################################'

                    if h.invoice_id:
                        tasa = 1
                        if h.invoice_id.currency_id.name == "USD":
                            tasa = self.obtener_tasa(h.invoice_id)
                        if h.invoice_id.fecha_importacion:
                            date_impor = h.invoice_id.fecha_importacion
                            emission_date = datetime.strftime(
                                datetime.strptime(str(date_impor), DEFAULT_SERVER_DATE_FORMAT),
                                format_new)
                            total = h.invoice_id.amount_total * tasa
                        else:
                            date_impor = h.invoice_id.invoice_date
                            emission_date = datetime.strftime(
                                datetime.strptime(str(date_impor), DEFAULT_SERVER_DATE_FORMAT),
                                format_new)

                        planilla = h.invoice_id.nro_planilla_impor
                        expediente = h.invoice_id.nro_expediente_impor




                    else:
                        date_impor = h.iwdl_id.invoice_id.fecha_importacion
                        emission_date = datetime.strftime(
                            datetime.strptime(str(date_impor), DEFAULT_SERVER_DATE_FORMAT),
                            format_new)
                        planilla = h.iwdl_id.invoice_id.nro_planilla_impor
                        expediente = h.iwdl_id.invoice_id.nro_expediente_impor
                        tasa = 1
                        if h.iwdl_id.invoice_id.currency_id.name == "USD":
                            tasa = self.obtener_tasa(h.iwdl_id.invoice_id)
                        total = h.iwdl_id.invoice_id.amount_total * tasa
                    get_wh_vat = 0.0
                    vat_reduced_base = 0
                    vat_reduced_rate = 0
                    vat_reduced_tax = 0
                    vat_additional_base = 0
                    vat_additional_rate = 0
                    vat_additional_tax = 0
                    'ALICUOTA GENERAL IMPORTACIONES'
                    vat_general_base_importaciones = h.vat_general_base
                    vat_general_rate_importaciones = (
                            h.vat_general_base and h.vat_general_tax * 100 / h.vat_general_base)
                    vat_general_rate_importaciones = round(vat_general_rate_importaciones, 0)
                    vat_general_tax_importaciones = h.vat_general_tax
                    'ALICUOTA REDUCIDA IMPORTACIONES'
                    vat_reduced_base_importaciones = h.vat_reduced_base
                    vat_reduced_rate_importaciones = int(
                        h.vat_reduced_base and h.vat_reduced_tax * 100 / h.vat_reduced_base)
                    vat_reduced_tax_importaciones = h.vat_reduced_tax
                    'ALICUOTA ADICIONAL IMPORTACIONES'
                    vat_additional_base_importaciones = h.vat_additional_base
                    vat_additional_rate_importaciones = int(
                        h.vat_additional_base and h.vat_additional_tax * 100 / h.vat_additional_base)
                    vat_additional_tax_importaciones = h.vat_additional_tax
                    'Suma total compras con IVA'
                    sum_total_with_iva = (
                            h.fb_id.base_amount + h.fb_id.tax_amount) if h.emission_date >= date_start.date() else 0
                    sum_total_with_iva_ajustes = (
                            h.fb_id.base_amount + h.fb_id.tax_amount) if h.emission_date < date_start.date() else 0
                    # Total monto con IVA
                    'SUMA TOTAL DE TODAS LAS ALICUOTAS PARA LAS IMPORTACIONES'
                    sum_vat_general_base_importaciones += h.vat_general_base + h.vat_reduced_base + h.vat_additional_base  # Base Imponible Alicuota general
                    sum_vat_general_tax_importaciones += h.vat_general_tax + h.vat_additional_tax + h.vat_reduced_tax  # Impuesto de IVA

                    'Suma total de Alicuota General'
                    suma_base_general_importaciones += h.vat_general_base
                    sum_base_general_tax_importaciones += h.vat_general_tax

                    ' Suma total de Alicuota Reducida'
                    sum_vat_reduced_base_importaciones += h.vat_reduced_base  # Base Imponible de alicuota Reducida
                    sum_vat_reduced_tax_importaciones += h.vat_reduced_tax  # Impuesto de IVA alicuota reducida
                    'Suma total de Alicuota Adicional'
                    sum_vat_additional_base_importaciones += h.vat_additional_base  # BASE IMPONIBLE ALICUOTA ADICIONAL
                    sum_vat_additional_tax_importaciones += h.vat_additional_tax  # IMPUESTO DE IVA ALICUOTA ADICIONAL

                    get_wh_vat = h.get_wh_vat
                sum_get_wh_vat += h.get_wh_vat  # IVA RETENIDO

                if h_vat_general_base != 0:
                    valor_base_imponible = h.vat_general_base
                    valor_alic_general = h_vat_general_rate
                    valor_iva = h_vat_general_tax
                else:

                    valor_base_imponible = 0
                    valor_alic_general = 0
                    valor_iva = 0

                # if get_wh_vat != 0:
                #     hola = get_wh_vat
                # else:
                #     hola = 0

                if h.vat_exempt != 0:
                    vat_exempt = h.vat_exempt

                else:
                    vat_exempt = 0

                'Para las diferentes alicuotas que pueda tener el proveedor  internacional'
                'todas son mayor a 0'
                if vat_general_rate_importaciones > 0 and vat_reduced_rate_importaciones > 0 and vat_additional_rate_importaciones > 0:
                    vat_general_general_rate_importaciones = str(vat_general_rate_importaciones) + ',' + ' ' + str(
                        vat_reduced_rate_importaciones) + ',' + ' ' + str(vat_additional_rate_importaciones) + ' '
                'todas son cero'
                if vat_general_rate_importaciones == 0 and vat_reduced_rate_importaciones == 0 and vat_additional_rate_importaciones == 0:
                    vat_general_general_rate_importaciones = 0
                'Existe reducida y adicional'
                if vat_general_rate_importaciones == 0 and vat_reduced_rate_importaciones > 0 and vat_additional_rate_importaciones > 0:
                    vat_general_general_rate_importaciones = str(vat_reduced_rate_importaciones) + ',' + ' ' + str(
                        vat_additional_rate_importaciones) + ' '
                'Existe general y adicional'
                if vat_general_rate_importaciones > 0 and vat_reduced_rate_importaciones == 0 and vat_additional_rate_importaciones > 0:
                    vat_general_general_rate_importaciones = str(vat_general_rate_importaciones) + ',' + ' ' + str(
                        vat_additional_rate_importaciones) + ' '
                'Existe general y reducida'
                if vat_general_rate_importaciones > 0 and vat_reduced_rate_importaciones > 0 and vat_additional_rate_importaciones == 0:
                    vat_general_general_rate_importaciones = str(vat_general_rate_importaciones) + ',' + ' ' + str(
                        vat_reduced_rate_importaciones) + ' '
                'Existe solo la general'
                if vat_general_rate_importaciones > 0 and vat_reduced_rate_importaciones == 0 and vat_additional_rate_importaciones == 0:
                    vat_general_general_rate_importaciones = str(vat_general_rate_importaciones)
                'Existe solo la reducida'
                if vat_general_rate_importaciones == 0 and vat_reduced_rate_importaciones > 0 and vat_additional_rate_importaciones == 0:
                    vat_general_general_rate_importaciones = str(vat_reduced_rate_importaciones)
                'Existe solo la adicional'
                if vat_general_rate_importaciones == 0 and vat_reduced_rate_importaciones == 0 and vat_additional_rate_importaciones > 0:
                    vat_general_general_rate_importaciones = str(vat_additional_rate_importaciones)
                #if h.emission_date >= date_start.date():

                if h.invoice_id:
                    no_deducible = h.invoice_id.no_deducible
                if h.iwdl_id.invoice_id:
                    no_deducible = h.iwdl_id.invoice_id.no_deducible

                datos_compras.append({

                    'emission_date': datetime.strftime(
                        datetime.strptime(str(h.emission_date), DEFAULT_SERVER_DATE_FORMAT),
                        format_new) if h.emission_date else ' ',
                    'partner_vat': h.partner_vat if h.partner_vat else ' ',
                    'partner_name': h.partner_name,
                    'people_type': h.people_type,
                    'wh_number': h.wh_number if h.wh_number else ' ',
                    'invoice_number': h.invoice_number,
                    'invoice_id': h.invoice_id,
                    'affected_invoice': h.affected_invoice,
                    'ctrl_number': h.ctrl_number,
                    'debit_affected': h.numero_debit_credit if h.doc_type == 'N/DB' else False,
                    'credit_affected': h.numero_debit_credit if h.doc_type == 'N/CR' else False,
                    # h.credit_affected,
                    'type': h.void_form,
                    'doc_type': h.doc_type,
                    'origin': origin,
                    'number': number,
                    'total_with_iva': h.total_with_iva,
                    'vat_exempt': vat_exempt,
                    'compras_credit': compras_credit,
                    'vat_general_base': valor_base_imponible,
                    'vat_general_rate': valor_alic_general,
                    'vat_general_tax': valor_iva,
                    'vat_reduced_base': vat_reduced_base,
                    'vat_reduced_rate': vat_reduced_rate,
                    'vat_reduced_tax': vat_reduced_tax,
                    'vat_additional_base': vat_additional_base,
                    'vat_additional_rate': vat_additional_rate,
                    'vat_additional_tax': vat_additional_tax,
                    'get_wh_vat': h.get_wh_vat,
                    'vat_general_base_importaciones': vat_general_base_importaciones + vat_additional_base_importaciones + vat_reduced_base_importaciones,
                    'vat_general_rate_importaciones': vat_general_general_rate_importaciones,
                    'vat_general_tax_importaciones': vat_general_tax_importaciones + vat_reduced_tax_importaciones + vat_additional_tax_importaciones,
                    'nro_planilla': planilla,
                    'nro_expediente': expediente,
                    'company_name': h.fb_id.company_id.name,
                    'company_rif': h.fb_id.company_id.vat,
                    'company_street': h.fb_id.company_id.street,
                    'no_deducible': no_deducible,
                    'nro_expediente_impor': h.invoice_id.nro_expediente_impor,
                })
                # else:
                #     datos_compras_ajustes.append({

                #         'emission_date': datetime.strftime(
                #             datetime.strptime(str(h.emission_date), DEFAULT_SERVER_DATE_FORMAT),
                #             format_new) if h.emission_date else ' ',
                #         'partner_vat': h.partner_vat if h.partner_vat else ' ',
                #         'partner_name': h.partner_name,
                #         'people_type': h.people_type,
                #         'wh_number': h.wh_number if h.wh_number else ' ',
                #         'invoice_number': h.invoice_number,
                #         'invoice_id': h.invoice_id,
                #         'affected_invoice': h.affected_invoice,
                #         'ctrl_number': h.ctrl_number,
                #         'debit_affected': h.numero_debit_credit if h.doc_type == 'N/DB' else False,
                #         'credit_affected': h.numero_debit_credit if h.doc_type == 'N/CR' else False,
                #         # h.credit_affected,
                #         'type': h.void_form,
                #         'doc_type': h.doc_type,
                #         'origin': origin,
                #         'number': number,
                #         'total_with_iva': h.total_with_iva,
                #         'vat_exempt': vat_exempt,
                #         'compras_credit': compras_credit,
                #         'vat_general_base': valor_base_imponible,
                #         'vat_general_rate': valor_alic_general,
                #         'vat_general_tax': valor_iva,
                #         'vat_reduced_base': vat_reduced_base,
                #         'vat_reduced_rate': vat_reduced_rate,
                #         'vat_reduced_tax': vat_reduced_tax,
                #         'vat_additional_base': vat_additional_base,
                #         'vat_additional_rate': vat_additional_rate,
                #         'vat_additional_tax': vat_additional_tax,
                #         'get_wh_vat': h.get_wh_vat,
                #         'vat_general_base_importaciones': vat_general_base_importaciones + vat_additional_base_importaciones + vat_reduced_base_importaciones,
                #         'vat_general_rate_importaciones': vat_general_general_rate_importaciones,
                #         'vat_general_tax_importaciones': vat_general_tax_importaciones + vat_reduced_tax_importaciones + vat_additional_tax_importaciones,
                #         'nro_planilla': planilla,
                #         'nro_expediente': expediente,
                #         'company_name': h.fb_id.company_id.name,
                #         'company_rif': h.fb_id.company_id.rif,
                #         'company_street': h.fb_id.company_id.street
                #     })
        return datos_compras, datos_compras_ajustes

    def get_datas_ventas(self):
        datos_ventas = []
        datos_ventas_ajustes = []
        for rec in self:
            format_new = "%d/%m/%Y"

            # date_start =(data['form']['date_from'])
            # date_end =(data['form']['date_to'])

            fb_id = self.env.context['active_id']
            busq = self.env['account.fiscal.book'].search([('id', '=', fb_id)])
            date_start = datetime.strptime(str(self.date_start), DATE_FORMAT)
            date_end = datetime.strptime(str(self.date_end), DATE_FORMAT)
            # date_start = busq.period_start
            # date_end = busq.period_end
            fbl_obj = self.env['account.fiscal.book.line'].search(
                [('fb_id', '=', busq.id), ('accounting_date', '>=', date_start)
                 ], order='rank asc')

            suma_total_w_iva = 0
            suma_no_taxe_sale = 0
            suma_vat_general_base = 0
            suma_total_vat_general_base = 0
            suma_total_vat_general_tax = 0
            suma_total_vat_reduced_base = 0
            suma_total_vat_reduced_tax = 0
            suma_total_vat_additional_base = 0
            suma_total_vat_additional_tax = 0
            suma_vat_general_tax = 0
            suma_vat_reduced_base = 0
            suma_vat_reduced_tax = 0
            suma_vat_additional_base = 0
            suma_vat_additional_tax = 0
            suma_get_wh_vat = 0
            suma_ali_gene_addi = 0
            suma_ali_gene_addi_debit = 0
            total_ventas_base_imponible = 0
            total_ventas_debit_fiscal = 0

            suma_amount_tax = 0

            for line in fbl_obj:
                if line.vat_general_base != 0 or line.vat_reduced_base != 0 or line.vat_additional_base != 0 or line.vat_exempt != 0 or (
                        line.partner_name == 'ANULADA' and line.invoice_number):
                    vat_general_base = 0
                    vat_general_rate = 0
                    vat_general_tax = 0
                    vat_reduced_base = 0
                    vat_additional_base = 0
                    vat_additional_rate = 0
                    vat_additional_tax = 0
                    vat_reduced_rate = 0
                    vat_reduced_tax = 0

                    if line.type == 'ntp':
                        no_taxe_sale = line.vat_general_base
                    else:
                        no_taxe_sale = 0.0

                    if line.vat_reduced_base and line.vat_reduced_base != 0:
                        vat_reduced_base = line.vat_reduced_base
                        vat_reduced_rate = (
                                line.vat_reduced_base and line.vat_reduced_tax * 100 / line.vat_reduced_base)
                        vat_reduced_rate = int(round(vat_reduced_rate, 0))
                        vat_reduced_tax = line.vat_reduced_tax
                        suma_vat_reduced_base += line.vat_reduced_base
                        suma_vat_reduced_tax += line.vat_reduced_tax

                    if line.vat_additional_base and line.vat_additional_base != 0:
                        vat_additional_base = line.vat_additional_base
                        vat_additional_rate = (
                                line.vat_additional_base and line.vat_additional_tax * 100 / line.vat_additional_base)
                        vat_additional_rate = int(round(vat_additional_rate, 0))
                        vat_additional_tax = line.vat_additional_tax
                        suma_vat_additional_base += line.vat_additional_base
                        suma_vat_additional_tax += line.vat_additional_tax

                    if line.vat_general_base and line.vat_general_base != 0:
                        vat_general_base = line.vat_general_base
                        vat_general_rate = (line.vat_general_tax * 100 / line.vat_general_base)
                        vat_general_rate = int(round(vat_general_rate, 0))
                        vat_general_tax = line.vat_general_tax
                        suma_vat_general_base += line.vat_general_base
                        suma_vat_general_tax += line.vat_general_tax

                    if line.get_wh_vat:
                        suma_get_wh_vat += line.get_wh_vat
                    if vat_reduced_rate == 0:
                        vat_reduced_rate = ''
                    else:
                        vat_reduced_rate = str(vat_reduced_rate)
                    if vat_additional_rate == 0:
                        vat_additional_rate = ''
                    else:
                        vat_additional_rate = str(vat_additional_rate)
                    if vat_general_rate == 0:
                        vat_general_rate = ''

                    if vat_general_rate == '' and vat_reduced_rate == '' and vat_additional_rate == '':
                        vat_general_rate = 0

                    # if  line.void_form == '03-ANU' and line.invoice_number:
                    #     vat_general_base = 0
                    #     vat_general_rate = 0
                    #     vat_general_tax = 0
                    #     vat_reduced_base = 0
                    #     vat_additional_base = 0
                    #     vat_additional_rate = 0
                    #     vat_additional_tax = 0
                    #     vat_reduced_rate = 0
                    #     vat_reduced_tax = 0
                    #if line.emission_date >= date_start.date():
                    datos_ventas.append({
                        'rannk': line.rank,
                        'emission_date': datetime.strftime(
                            datetime.strptime(str(line.emission_date), DEFAULT_SERVER_DATE_FORMAT), format_new),
                        'partner_vat': line.partner_vat if line.partner_vat else ' ',
                        'partner_name': line.partner_name,
                        'people_type': line.people_type if line.people_type else ' ',
                        'report_z': line.z_report,
                        'export_form': '',
                        'wh_number': line.wh_number,
                        'date_wh_number': line.iwdl_id.retention_id.date_ret if line.wh_number != '' else '',
                        'invoice_number': line.invoice_number,
                        'n_ultima_factZ': line.n_ultima_factZ,
                        'ctrl_number': line.ctrl_number,
                        'debit_note': line.numero_debit_credit if line.doc_type == 'N/DB' else False,
                        'credit_note': line.numero_debit_credit if line.doc_type == 'N/CR' else False,
                        'type': line.void_form,
                        'doc_type': line.doc_type,
                        'affected_invoice': line.affected_invoice if line.affected_invoice else ' ',
                        'total_w_iva': line.total_with_iva if line.total_with_iva else 0,
                        'no_taxe_sale': line.vat_exempt,
                        'export_sale': '',
                        'vat_general_base': vat_general_base,  # + vat_reduced_base + vat_additional_base,
                        'vat_general_rate': str(vat_general_rate),
                        # + '  ' + str(vat_reduced_rate) + ' ' + str(vat_additional_rate) + '  ',
                        'vat_general_tax': vat_general_tax,  # + vat_reduced_tax + vat_additional_tax,
                        'vat_reduced_base': line.vat_reduced_base,
                        'vat_reduced_rate': str(vat_reduced_rate),
                        'vat_reduced_tax': vat_reduced_tax,
                        'vat_additional_base': vat_additional_base,
                        'vat_additional_rate': str(vat_additional_rate),
                        'vat_additional_tax': vat_additional_tax,
                        'get_wh_vat': line.get_wh_vat,
                        'company_name': line.fb_id.company_id.name,
                        'company_rif': line.fb_id.company_id.rif
                    })
                    # else:
                    #     datos_ventas_ajustes.append({
                    #         'rannk': line.rank,
                    #         'emission_date': datetime.strftime(
                    #             datetime.strptime(str(line.emission_date), DEFAULT_SERVER_DATE_FORMAT), format_new),
                    #         'partner_vat': line.partner_vat if line.partner_vat else ' ',
                    #         'partner_name': line.partner_name,
                    #         'people_type': line.people_type if line.people_type else ' ',
                    #         'report_z': line.z_report,
                    #         'export_form': '',
                    #         'wh_number': line.wh_number,
                    #         'date_wh_number': line.iwdl_id.retention_id.date_ret if line.wh_number != '' else '',
                    #         'invoice_number': line.invoice_number,
                    #         'n_ultima_factZ': line.n_ultima_factZ,
                    #         'ctrl_number': line.ctrl_number,
                    #         'debit_note': line.numero_debit_credit if line.doc_type == 'N/DB' else False,
                    #         'credit_note': line.numero_debit_credit if line.doc_type == 'N/CR' else False,
                    #         'type': line.void_form,
                    #         'doc_type': line.doc_type,
                    #         'affected_invoice': line.affected_invoice if line.affected_invoice else ' ',
                    #         'total_w_iva': line.total_with_iva if line.total_with_iva else 0,
                    #         'no_taxe_sale': line.vat_exempt,
                    #         'export_sale': '',
                    #         'vat_general_base': vat_general_base,  # + vat_reduced_base + vat_additional_base,
                    #         'vat_general_rate': str(vat_general_rate),
                    #         # + '  ' + str(vat_reduced_rate) + ' ' + str(vat_additional_rate) + '  ',
                    #         'vat_general_tax': vat_general_tax,  # + vat_reduced_tax + vat_additional_tax,
                    #         'vat_reduced_base': line.vat_reduced_base,
                    #         'vat_reduced_rate': str(vat_reduced_rate),
                    #         'vat_reduced_tax': vat_reduced_tax,
                    #         'vat_additional_base': vat_additional_base,
                    #         'vat_additional_rate': str(vat_additional_rate),
                    #         'vat_additional_tax': vat_additional_tax,
                    #         'get_wh_vat': line.get_wh_vat,
                    #         'company_name': line.fb_id.company_id.name,
                    #         'company_rif': line.fb_id.company_id.rif
                    #     })
                    suma_total_w_iva += line.total_with_iva
                    suma_no_taxe_sale += line.vat_exempt
                    suma_total_vat_general_base += line.vat_general_base
                    suma_total_vat_general_tax += line.vat_general_tax
                    suma_total_vat_reduced_base += line.vat_reduced_base
                    suma_total_vat_reduced_tax += line.vat_reduced_tax
                    suma_total_vat_additional_base += line.vat_additional_base
                    suma_total_vat_additional_tax += line.vat_additional_tax

                    # RESUMEN LIBRO DE VENTAS

                    # suma_ali_gene_addi =  suma_vat_additional_base if line.vat_additional_base else 0.0
                    # suma_ali_gene_addi_debit = suma_vat_additional_tax if line.vat_additional_tax else 0.0
                    total_ventas_base_imponible = suma_vat_general_base + suma_vat_additional_base + suma_vat_reduced_base + suma_no_taxe_sale
                    total_ventas_debit_fiscal = suma_vat_general_tax + suma_vat_additional_tax + suma_vat_reduced_tax

            if fbl_obj.env.company and fbl_obj.env.company.street:
                street = str(fbl_obj.env.company.street) + ','
            else:
                street = ' '

        return datos_ventas, datos_ventas_ajustes