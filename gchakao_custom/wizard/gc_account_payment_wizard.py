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

class ClassName(models.TransientModel):
    _name = 'gc.account.payment.wizard'
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
    partner_ids = fields.Many2many('res.partner', string='Vendedore(s)')
    journal_ids = fields.Many2many('account.journal', string='Diario(s)')
    user_ids = fields.Many2many('res.users', string='Usuario(s)')
    report = fields.Binary('Archivo listo', filters='.xls', readonly=True)
    name = fields.Char('Nombre del archivo', size=32)
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
        name = 'Pagos'
        if self.range == 'month':
            month_label = dict(self.fields_get("month", "selection")["month"]["selection"])
            return f'{name} de {month_label[self.month]}/{self.year}'
        elif self.range == 'dates':
            return f'{name} de {self.date_start.strftime("%d/%m/%Y")} AL {self.date_end.strftime("%d/%m/%Y")}'
        elif self.range == 'date':
            return f'{name} de {self.date_def.strftime("%d/%m/%Y")}'
        else:
            return f'{name} (Todos)'

    def diarios_excluidos(self):
        return self.env['account.journal'].search([('name','ilike','caja efectivo asesor')]).ids

    def usuarios_internos(self):
        return self.env['res.users'].search([('share','=',False)]).ids

    def _get_domain(self):
        domain = [
            ('company_id', '=', self.company_id.id),
            ('payment_type', '=', 'inbound'),
            ('state', 'in', ('posted','reconciled')),
            ('journal_id', 'not in', self.diarios_excluidos()),
        ]

        if len(self.partner_ids) > 0:
            domain.append(('partner_id','in',self.partner_ids.ids))
        if len(self.journal_ids) > 0:
            domain.append(('journal_id','in',self.journal_ids.ids))
        if len(self.user_ids) > 0:
            domain.append(('create_uid','in',self.user_ids.ids))
        else:
            domain.append(('create_uid','in',self.usuarios_internos()))
        if self.range == 'dates' or self.range == 'month':
            domain.append(('date', '>=', self.date_start))
            domain.append(('date', '<=', self.date_end))
        elif self.range == 'date':
            domain.append(('date', '=', self.date_def))
        return domain

    def formato_fecha(self, date):
        dia = str(date.day)
        mes = str(date.month)
        anio = str(date.year)
        result=dia.zfill(2)+"/"+mes.zfill(2)+"/"+anio[2:]
        return result

    def _prepare_report_data(self):
        result = []
        domain = self._get_domain()
        payments = self.env['account.payment'].sudo().search(domain)
        if not payments:
            raise UserError('No hay datos para mostrar')
        
        journal_ids = []
        for payment in payments.sorted(key=lambda r: -r.id):

            if 'extra' in payment.name.lower():
                continue

            efectivo_bs = 0
            efectivo_dollar = 0
            banco_bs = 0
            banco_dollar = 0
            asiento_dollar = 0
            asiento_bs = 0
            total_bs = 0
            total_usd = 0

            rate = self.env['res.currency.rate'].search([
                ('currency_id.name', '=', 'USD'),
                ('name', '<=', payment.date),
            ], limit=1).rate
            
            if payment.tax_today:
                rate = payment.tax_today

            if not payment.journal_id.id in journal_ids:
                journal_ids.append(payment.journal_id.id)

            if payment.currency_id.id == payment.company_id.currency_id.id:
                total_bs = payment.amount
                total_usd = payment.amount / rate
            else:
                total_bs = payment.amount * rate
                total_usd = payment.amount
            if payment.journal_id.type in ('cash', 'bank'):
                if payment.journal_id.type == 'cash':
                    if payment.currency_id.id == payment.company_id.currency_id.id:
                        efectivo_bs = payment.amount
                    else:
                        efectivo_dollar = payment.amount
                elif payment.journal_id.type == 'bank':
                    if payment.currency_id.id == payment.company_id.currency_id.id:
                        banco_bs = payment.amount
                    else:
                        banco_dollar = payment.amount
            else:
                if payment.currency_id.id == payment.company_id.currency_id.id:
                    asiento_bs = payment.amount
                else:
                    asiento_dollar = payment.amount

            invoice_num = []
            if len(payment.reconciled_invoice_ids)>0:
                for invoice in payment.reconciled_invoice_ids:
                    invoice_num.append(invoice.invoice_number)

            res = {
                'name': self.formato_fecha(payment.date),
                'invoice_num': ", ".join(invoice_num or ''),
                'partner_id': payment.partner_id.name,
                'payment_name': payment.name,
                'currency_rate': rate,
                'total_bs': total_bs,
                'total_usd': total_usd,
                'efectivo_bs':efectivo_bs,
                'efectivo_dollar':efectivo_dollar,
                'banco_bs': banco_bs,
                'banco_dollar':banco_dollar,
                'asiento_bs': asiento_bs,
                'asiento_dollar':asiento_dollar,
                'journal_id': payment.journal_id.id,
                'journal_name': payment.journal_id.name,
                'amount': payment.amount,
                'currency_id': payment.currency_id.id,
            }
            result.append(res)

        totales = []
        journal_ids.sort()
        jornal_name = currency_name = False
        for journal in journal_ids:
            amount = amount_dollar = 0
            for payment in payments.sorted(lambda j: j.journal_id):

                if 'extra' in payment.name.lower():
                    continue

                rate = self.env['res.currency.rate'].search([
                    ('currency_id.name', '=', 'USD'),
                    ('name', '<=', payment.date),
                ], limit=1).rate
                
                if payment.tax_today:
                    rate = payment.tax_today

                if payment.journal_id.id == journal:
                    jornal_name = payment.journal_id.name
                    currency_name = payment.currency_id.name if payment.currency_id else 'Bs'
                    if payment.currency_id.id != payment.company_id.currency_id.id:
                        amount += payment.amount * rate
                        amount_dollar += payment.amount
                    else:
                        amount += payment.amount
                        amount_dollar += payment.amount / rate

            diarios_dict = {
                'name' : jornal_name,
                'amount': amount,
                'amount_dollar': amount_dollar,
                'currency_name' : currency_name,
            }
            totales.append(diarios_dict)

        asiento_igt_usd = 0
        asiento_igt_bs = 0
        igtf_ids = payments.filtered(lambda p: p.move_id_igtf_divisa).mapped('move_id_igtf_divisa')
        journal_igtf_ids = []
        if igtf_ids:
            for igtf in igtf_ids:
                if igtf.currency_id.id != igtf.company_id.currency_id.id:
                    asiento_igt_usd = igtf.amount_total
                    asiento_igt_bs = igtf.amount_total * igtf.tax_today
                else:
                    asiento_igt_usd = igtf.amount_total / igtf.tax_today
                    asiento_igt_bs = igtf.amount_total

                values = {
                    'diario_igtf_d': igtf.journal_id.id,
                    'diario_igtf_name': igtf.journal_id.name,
                    'asiento_igt_usd': asiento_igt_usd,
                    'asiento_igt_bs': asiento_igt_bs,
                }
                if not any(res['diario_igtf_d'] == igtf.journal_id.id for res in journal_igtf_ids):
                    journal_igtf_ids.append(values)
                else:
                    for res in journal_igtf_ids:
                        if res['diario_igtf_d'] == igtf.journal_id.id:
                            res['asiento_igt_usd'] += values['asiento_igt_usd']
                            res['asiento_igt_bs'] += values['asiento_igt_bs']

        data = {
            'nombre_reporte': self._get_name_report().upper(),
            'form': result,
            'diarios': totales,
            'journal_igtf_ids': journal_igtf_ids,
            'company': self.company_id.name,
            'ruc': self.company_id.vat,
            'date_now': self.date_now,
        }
        return data

    def action_print_pdf(self):
        self.ensure_one()
        data = self._prepare_report_data()
        return self.env.ref('gchakao_custom.action_gc_account_payment_report').report_action([], data=data)


    def generate_xls_report(self):
        wb1 = xlwt.Workbook(encoding='utf-8')
        ws1 = wb1.add_sheet('Resumen')
        fp = BytesIO()

        date_format = xlwt.XFStyle()
        date_format.num_format_str = 'dd/mm/yyyy'

        number_format = xlwt.XFStyle()
        number_format.num_format_str = '#,##0.00'

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

        ws1.write_merge(row,row, 1, 1, "Fecha",header_style)
        ws1.write_merge(row,row, 2, 2, "N° de Factura",header_style)
        ws1.write_merge(row,row, 3, 4, "Ref. Pago",header_style)
        ws1.write_merge(row,row, 5, 7, "Cliente",header_style)
        ws1.write_merge(row,row, 8, 8, "Tasa",header_style)
        ws1.write_merge(row,row, 9, 9, "Op Bs",header_style)
        ws1.write_merge(row,row, 10, 10, "Op $",header_style)
        ws1.write_merge(row,row, 11, 11, "Efectivo Bs",header_style)
        ws1.write_merge(row,row, 12, 12, "Efectivo $",header_style)
        ws1.write_merge(row,row, 13, 13, "Banco Bs",header_style)
        ws1.write_merge(row,row, 14, 14, "Banco $",header_style)
        ws1.write_merge(row,row, 15, 15, "Asiento bs",header_style)
        ws1.write_merge(row,row, 16, 16, "Asiento $",header_style)

        total_bs = total_usd = efectivo_bs = efectivo_dollar = banco_bs = banco_dollar = asiento_bs = asiento_dollar = 0
        for data in datas['form']:
            row += 1
            ws1.write_merge(row,row, 1, 1, data['name'],header_style_c)
            ws1.write_merge(row,row, 2, 2, data['invoice_num'],header_style_c)
            ws1.write_merge(row,row, 3, 4, data['payment_name'],header_style_c)
            ws1.write_merge(row,row, 5, 7, data['partner_id'],header_style_c)
            ws1.write_merge(row,row, 8, 8, data['currency_rate'],number_format)
            ws1.write_merge(row,row, 9, 9, data['total_bs'],number_format)
            ws1.write_merge(row,row, 10, 10, data['total_usd'],number_format)
            ws1.write_merge(row,row, 11, 11, data['efectivo_bs'],number_format)
            ws1.write_merge(row,row, 12, 12, data['efectivo_dollar'],number_format)
            ws1.write_merge(row,row, 13, 13, data['banco_bs'],number_format)
            ws1.write_merge(row,row, 14, 14, data['banco_dollar'],number_format)
            ws1.write_merge(row,row, 15, 15, data['asiento_bs'],number_format)
            ws1.write_merge(row,row, 16, 16, data['asiento_dollar'],number_format)
            total_bs += data['total_bs']
            total_usd += data['total_usd']
            efectivo_bs += data['efectivo_bs']
            efectivo_dollar += data['efectivo_dollar']
            banco_bs += data['banco_bs']
            banco_dollar += data['banco_dollar']
            asiento_bs += data['asiento_bs']
            asiento_dollar += data['asiento_dollar']

        row += 1
        ws1.write_merge(row,row, 1, 8, 'TOTALES',header_style)
        ws1.write_merge(row,row, 9, 9, total_bs, number_format)
        ws1.write_merge(row,row, 10, 10, total_usd, number_format)
        ws1.write_merge(row,row, 11, 11, efectivo_bs, number_format)
        ws1.write_merge(row,row, 12, 12, efectivo_dollar, number_format)
        ws1.write_merge(row,row, 13, 13, banco_bs, number_format)
        ws1.write_merge(row,row, 14, 14, banco_dollar, number_format)
        ws1.write_merge(row,row, 15, 15, asiento_bs, number_format)
        ws1.write_merge(row,row, 16, 16, asiento_dollar, number_format)

        row += 2
        existe = False
        total_bs = 0
        total_usd = 0
        for diario in datas['diarios']:
            ws1.write_merge(row,row, 3, 6, f"{diario['name']} ({diario['currency_name']}):", header_style_diarios)
            ws1.write_merge(row,row, 7, 7, diario['amount_dollar'], number_format)
            ws1.write_merge(row,row, 8, 8, diario['amount'], number_format)
            total_usd += diario['amount_dollar']
            total_bs += diario['amount']
            row += 1

        ws1.write_merge(row,row, 7, 7, total_usd, number_format)
        ws1.write_merge(row,row, 8, 8, total_bs, number_format)

        wb1.save(fp)
        out = base64.b64encode(fp.getvalue())
        fecha  = datetime.now().strftime('%d/%m/%Y')
        self.write({'state': 'get', 'report': out, 'name':'Cierre_de_ventas_diario.xls'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'gc.account.payment.wizard',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }