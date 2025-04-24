# Copyright YEAR(S), AUTHOR(S)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, api
from odoo.exceptions import UserError
from datetime import date, datetime, time, timedelta
import pytz
import calendar
import re
import json
import io
from io import BytesIO
import xlsxwriter
import shutil
import base64
import csv
import xlwt


YEAR_REGEX = re.compile("^[0-9]{4}$")
DATE_FORMAT = '%Y-%m-%d'

MONTH_SELECTION = [('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'), ('5', 'Mayo'),
                   ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'), ('9', 'Setiembre'), ('10', 'Octubre'),
                   ('11', 'Noviembre'), ('12', 'Diciembre')]

class GcaccountPaymentIgtfWizard(models.TransientModel):
    _name = 'gc.account.payment.igtf.wizard'
    _description = 'Parametros para reporte de cierre diario'

    def _default_month(self):
        user_tz = self.env.user.tz or 'America/Caracas'
        timezone = pytz.timezone(user_tz)
        current = datetime.now(timezone)
        return str(current.month)

    def _default_year(self):
        user_tz = self.env.user.tz or 'America/Caracas'
        timezone = pytz.timezone(user_tz)
        current = datetime.now(timezone)
        return str(current.year)

    range = fields.Selection([
        ('date', 'Por día'),
        ('month', 'Por mes'),
        ('dates', 'Rango de fechas'),
        ('all', 'Todos'),
    ], 'Fecha', default='date', required=True)

    month = fields.Selection(MONTH_SELECTION, string='Mes', default=_default_month)
    year = fields.Char('Año', default=_default_year)    
    date_start = fields.Date(string='Desde',)
    date_end = fields.Date(string='Hasta',)
    date_now = fields.Datetime(string='Fecha', default=lambda *a:datetime.now())
    company_id = fields.Many2one('res.company','Compañia',default=lambda self: self.env.company.id)
    partner_type = fields.Selection([('cliente', 'Clientes'), ('proveedor', 'Proveedores')], default='cliente')
    
    report = fields.Binary('Archivo listo', filters='.xls', readonly=True)
    name = fields.Char('Nombre del archivo', size=100)
    state = fields.Selection([('choose', 'choose'), ('get', 'get')],default='choose')

    def _get_current_date(self):
        """ :return current date """
        return datetime.now(pytz.timezone(self.env.user.tz or 'America/Caracas'))

    date_def = fields.Date('Día', default=lambda self: self._get_current_date())

    @api.onchange('year')
    def onchange_year(self):
        if self.year is False or not bool(YEAR_REGEX.match(self.year)):
            raise ValidationError('Debe especificar un año correcto')

    @api.constrains('date_start', 'date_end')
    def check_dates(self):
        if self.date_start is not False and \
                self.date_end is not False:
            if self.date_end < self.date_start:
                raise ValidationError('La fecha de inicio debe ser menor o igual que la fecha de fin')

    @api.onchange('range', 'month')
    def onchange_range(self):
        if self.range == 'month':
            w, days = calendar.monthrange(int(self.year), int(self.month))
            self.date_start = datetime.strptime('{}-{}-{}'.format(self.year, self.month, 1), DATE_FORMAT).date()
            self.date_end = datetime.strptime('{}-{}-{}'.format(self.year, self.month, days), DATE_FORMAT).date()

    @api.constrains('date_start', 'date_end')
    def check_parameters(self):
        for record in self:
            if record.date_start and record.date_end:
                if record.date_start > record.date_end:
                    raise ValidationError('La fecha de fin debe ser mayor que la de inicio')

    def _get_name_report(self):
        name = 'Resumen IGTF percibido'
        if self.range == 'month':
            month_label = dict(self.fields_get("month", "selection")["month"]["selection"])
            return f'{name} de {month_label[self.month]}/{self.year}'
        elif self.range == 'dates':
            return f'{name} de {self.date_start.strftime("%d/%m/%Y")} AL {self.date_end.strftime("%d/%m/%Y")}'
        elif self.range == 'date':
            return f'{name} de {self.date_def.strftime("%d/%m/%Y")}'
        else:
            return f'{name} (Todos)'

    def _get_domain_payment(self):
        domain = [
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'posted'),
            ('aplicar_igtf_divisa', '=', True),
        ]

        if self.partner_type == 'proveedor':
            domain.append(('payment_type', '=', 'outbound'))
        else:
            domain.append(('payment_type', '=', 'inbound'))
        if self.range == 'dates' or self.range == 'month':
            domain.append(('move_id.date', '>=', self.date_start))
            domain.append(('move_id.date', '<=', self.date_end))
        elif self.range == 'date':
            domain.append(('move_id.date', '=', self.date_def))
        return domain

    def formato_fecha(self, date):
        dia = str(date.day)
        mes = str(date.month)
        anio = str(date.year)
        result=dia.zfill(2)+"/"+mes.zfill(2)+"/"+anio[2:]
        return result

    def _prepare_report_data(self):
        result = []
        domain_payment = self._get_domain_payment()
        payments = self.env['account.payment'].sudo().search(domain_payment)
        moves = self.env['account.move'].search([('company_id', '=', self.company_id.id)])

        if not payments:
            raise UserError('No hay datos para mostrar')
        
        journal_ids = []
        cont = 0
        for payment in payments.sorted(key=lambda p: p.id):
            cont += 1
            res = {
                'cont': cont,
                'invoice_date': self.formato_fecha(payment.move_id.date),
                'invoice_number': 'ANT',
                'invoice_number_ctrl': 'ANT',
                'rif': payment.partner_id.rif,
                'partner': payment.partner_id.name,
                'payment_date': self.formato_fecha(payment.move_id.date),
                'amount_dollar': payment.amount if payment.currency_id.id != payment.company_id.currency_id.id else payment.amount / payment.tax_today or 1,
                'rate': payment.tax_today,
                'amount_untaxed_bs': payment.amount if payment.currency_id.id == payment.company_id.currency_id.id else payment.amount * payment.tax_today or 1,
                'aliquot': payment.company_id.igtf_divisa_porcentage,
                'amount_total': payment.mount_igtf if payment.currency_id.id == payment.company_id.currency_id.id else payment.mount_igtf * payment.tax_today or 1,
            }
            if payment.invoice_ids:
                res['invoice_number'] = payment.invoice_ids[0].invoice_number
                res['invoice_number_ctrl'] = payment.invoice_ids[0].nro_ctrl

            if not res:
                pass
            
            result.append(res)

        data = {
            'nombre_reporte': self._get_name_report().upper(),
            'form': result,
            'ruc': self.company_id.vat,
            'date_now': self.date_now,
        }
        return data

    def action_print_pdf(self):
        self.ensure_one()
        data = self._prepare_report_data()
        return self.env.ref('gchakao_custom.action_gc_account_payment_igtf_report').report_action([], data=data)


    def generate_xls_report(self):
        wb1 = xlwt.Workbook(encoding='utf-8')
        ws1 = wb1.add_sheet('Resumen')
        fp = BytesIO()

        date_format = xlwt.XFStyle()
        date_format.num_format_str = 'dd/mm/yyyy'

        number_format = xlwt.XFStyle()
        number_format.num_format_str = '#,##0.0000'

        header_content_style = xlwt.easyxf("font: name Helvetica size 20 px, bold 1, height 170;")
        header_content_style_c = xlwt.easyxf("font: name Helvetica size 20 px, bold 1, height 170; align: horiz center")
        sub_header_style = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: left thin, right thin, top thin, bottom thin;")
        sub_header_style_c = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: left thin, right thin, top thin, bottom thin; align: horiz center")
        sub_header_style_r = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: left thin, right thin, top thin, bottom thin; align: horiz right")

        header_style = xlwt.easyxf("font: name Helvetica size 10 px, height 170; borders: left thin, right thin, top thin, bottom thin; align: horiz center")
        header_style_diarios = xlwt.easyxf("font: name Helvetica size 10 px, height 170; borders: left thin, right thin, top thin, bottom thin;")
        header_style_c = xlwt.easyxf("font: name Helvetica size 10 px, height 170; align: horiz center")
        header_style_r = xlwt.easyxf("font: name Helvetica size 10 px, height 170; align: horiz right")

        sub_header_content_style = xlwt.easyxf("font: name Helvetica size 10 px, height 170;")
        line_content_style = xlwt.easyxf("font: name Helvetica, height 170;")
        row = 0
        col = 0
        ws1.row(row).height = 500

        ################ Cuerpo del excel ################

        ws1.write_merge(row,row, 4, 9, "Razón Social:"+" "+str(self.company_id.name), sub_header_style)
        row=row+1
        ws1.write_merge(row, row, 4, 9,"Rif:"+" "+str(self.company_id.partner_id.vat), sub_header_style)
        row=row+1
        ws1.write_merge(row,row, 4, 9, "Transacciones de Ventas",sub_header_style_c)
        row=row+1
        ws1.write_merge(row,row, 4, 9,self._get_name_report(), sub_header_style_c)
        row += 1
        ws1.write_merge(row,row, 4, 4, "Fecha",sub_header_style_c)
        ws1.write_merge(row,row, 5, 5, self.formato_fecha(self.date_now),sub_header_style_c)

        datas = self._prepare_report_data()
        row += 2
        ############### Cabecera #########################

        ws1.write_merge(row,row, 1, 1, "N° de Operación",header_style)
        ws1.write_merge(row,row, 2, 2, "Fecha",header_style)
        ws1.write_merge(row,row, 3, 4, "N° de Factura",header_style)
        ws1.write_merge(row,row, 5, 7, "N° de Control",header_style)
        ws1.write_merge(row,row, 8, 8, "Rif",header_style)
        ws1.write_merge(row,row, 9, 9, "Cliente",header_style)
        ws1.write_merge(row,row, 10, 10, "Fecha de pago",header_style)
        ws1.write_merge(row,row, 11, 11, "Monto en $",header_style)
        ws1.write_merge(row,row, 12, 12, "Tasa",header_style)
        ws1.write_merge(row,row, 13, 13, "Base Imp Bs",header_style)
        ws1.write_merge(row,row, 14, 14, "Alicuota %",header_style)
        ws1.write_merge(row,row, 15, 15, "IGTF Percibido",header_style)

        acum_amount_dollar = acum_amount_untaxed_bs = acum_amount_total = total_operations = cont = 0
        for data in datas['form']:
            row += 1
            cont += 1
            ws1.write_merge(row,row, 1, 1, cont,header_style_c)
            ws1.write_merge(row,row, 2, 2, data['invoice_date'],date_format)
            ws1.write_merge(row,row, 3, 4, data['invoice_number'],header_style_c)
            ws1.write_merge(row,row, 5, 7, data['invoice_number_ctrl'],header_style_c)
            ws1.write_merge(row,row, 8, 8, data['rif'],number_format)
            ws1.write_merge(row,row, 9, 9, data['partner'],number_format)
            ws1.write_merge(row,row, 10, 10, data['payment_date'],date_format)
            ws1.write_merge(row,row, 11, 11, data['amount_dollar'],number_format)
            ws1.write_merge(row,row, 12, 12, data['rate'],number_format)
            ws1.write_merge(row,row, 13, 13, data['amount_untaxed_bs'],number_format)
            ws1.write_merge(row,row, 14, 14, data['aliquot'],number_format)
            ws1.write_merge(row,row, 15, 15, data['amount_total'],number_format)
            # ACUMULADORES
            acum_amount_dollar += data['amount_dollar']
            acum_amount_untaxed_bs += data['amount_untaxed_bs']
            acum_amount_total += data['amount_total']
            total_operations = data['cont']

        row += 1
        ws1.write_merge(row,row, 1, 10, 'TOTALES',header_style)
        ws1.write_merge(row,row, 11, 11, acum_amount_dollar, number_format)
        ws1.write_merge(row,row, 12, 12, '', header_style_c)
        ws1.write_merge(row,row, 13, 13, acum_amount_untaxed_bs, number_format)
        ws1.write_merge(row,row, 14, 14, '', header_style_c)
        ws1.write_merge(row,row, 15, 15, acum_amount_total, number_format)

        row += 2
        ws1.write_merge(row,row, 4, 4, 'Alícuota',header_style)
        ws1.write_merge(row,row, 5, 6, 'Concepto',header_style)
        ws1.write_merge(row,row, 7, 8, 'Cantidad de Operaciones',header_style)
        ws1.write_merge(row,row, 9, 10, 'Base Imponible (Bs.)',header_style)
        row += 1
        ws1.write_merge(row,row, 4, 4,  '3%', header_style)
        ws1.write_merge(row,row, 5, 6,  'Efectivo en moneda extranjera', header_style)
        ws1.write_merge(row,row, 7, 8,  total_operations, number_format)
        ws1.write_merge(row,row, 9, 10, acum_amount_untaxed_bs, number_format)
        row += 1
        ws1.write_merge(row,row, 4, 4,  '3%', header_style)
        ws1.write_merge(row,row, 5, 6,  'Criptomonedas', header_style)
        ws1.write_merge(row,row, 7, 8,  0.00, number_format)
        ws1.write_merge(row,row, 9, 10, 0.00, number_format)
        row += 1
        ws1.write_merge(row,row, 4, 4,  '3%', header_style)
        ws1.write_merge(row,row, 5, 6,  'Criptoactivos', header_style)
        ws1.write_merge(row,row, 7, 8,  0.00, number_format)
        ws1.write_merge(row,row, 9, 10, 0.00, number_format)
        row += 1
        ws1.write_merge(row,row, 4, 8, 'Monto Total de la Base Imponible (Bs.) 3%', header_style)
        ws1.write_merge(row,row, 9, 10, acum_amount_untaxed_bs, number_format)

        row += 2
        ws1.write_merge(row,row, 4, 10, 'RESUMEN',header_style)
        row += 1
        ws1.write_merge(row,row, 4, 8, 'Monto Total de las Operaciones de la Alicuota (Bs.) del 2%',header_style)
        ws1.write_merge(row,row, 9, 10, 0.00, number_format)
        row += 1
        ws1.write_merge(row,row, 4, 8, 'Monto Total de las Operaciones de la Alicuota (Bs.) del 3%',header_style)
        ws1.write_merge(row,row, 9, 10, acum_amount_total, number_format)
        row += 1
        ws1.write_merge(row,row, 4, 8, 'Monto Total a Pagar de las Alicuotas(Bs.) del (2% + 3%)',header_style)
        ws1.write_merge(row,row, 9, 10, acum_amount_total, number_format)

        wb1.save(fp)
        out = base64.b64encode(fp.getvalue())
        fecha  = datetime.now().strftime('%d/%m/%Y')
        file_name = self._get_name_report().upper().replace(' ','_')
        self.write({'state': 'get', 'report': out, 'name':f'{file_name}.xls'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'gc.account.payment.igtf.wizard',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
