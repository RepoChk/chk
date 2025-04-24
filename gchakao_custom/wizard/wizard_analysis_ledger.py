from datetime import datetime, timedelta
from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError
import logging

import os
import io
from io import BytesIO
from PIL import Image
import tempfile
import xlsxwriter
import shutil
import base64
import csv
import xlwt

_logger = logging.getLogger(__name__)


class WizardAnalysisLedger(models.TransientModel):
    _name = 'wizard.analysis.ledger'

    date_from = fields.Date(string='Date From', default=lambda *a:datetime.now().strftime('%Y-%m-%d'))
    date_to = fields.Date('Date To', default=lambda *a:(datetime.now() + timedelta(days=(1))).strftime('%Y-%m-%d'))
    date_now = fields.Datetime(string='Date Now', default=lambda *a:datetime.now())
    currency_id = fields.Many2one(comodel_name='res.currency', string='Currency')
    account_id = fields.Many2many('account.account', string='Cuentas')

    previous_amount = fields.Float(string='Monto Previo')

    state = fields.Selection([('choose', 'choose'), ('get', 'get')],default='choose')
    report = fields.Binary('Prepared file', filters='.xls', readonly=True)
    name = fields.Char('File Name', size=60)
    company_id = fields.Many2one(comodel_name='res.company', string='Compañía',default=lambda self: self.env.company.id)
    user_id = fields.Many2one(comodel_name='res.users', string='Usuario Activo', default=lambda x: x.env.uid)
    company_ids = fields.Many2many('res.company','analysis_ledger_company_rel','company_id','partner_id', string='Compañías', default=lambda self: self.env.company.ids)

    @api.onchange('user_id')
    def _onchange_user_id(self):
        companies = self.env['res.users'].search([('id', '=', self.user_id.id)]).company_ids.ids
        return {'domain': {'company_ids': [('id', 'in', companies)]}}

    # *******************  FORMATOS ****************************

    def float_format(self,valor):
        if valor:
            result = '{:,.2f}'.format(valor)
            result = result.replace(',','*')
            result = result.replace('.',',')
            result = result.replace('*','.')
        else:
            result="0,00"
        return result
    
    # *******************  REPORTE EN PDF ****************************
    def print_pdf(self):
        data = self._prepare_data()
        return self.env.ref('gchakao_custom.action_analysis_ledger_report').report_action([], data=data)
    # *******************  BÚSQUEDA DE DATOS ****************************

    def _prepare_data(self):
        results = []
        accounts = []
        previous = 0

        domainpa = [
            ('move_id.date', '<', self.date_from),
            ('parent_state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]

        if self.account_id:
            domainpa.append(('account_id', 'in', self.account_id.ids))

        paccount = self.env['account.move.line'].sudo().search(domainpa)

        for line in paccount:

            if self.currency_id.name == 'VES':
                previous += line.debit
                previous += line.credit
            elif self.currency_id.name == 'USD':
                previous += line.debit_usd
                previous += line.credit_usd

        current = previous
        self.previous_amount = previous

        domain = [
            ('move_id.date', '>=', self.date_from),
            ('move_id.date', '<=', self.date_to),
            ('parent_state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]

        if self.account_id:
            domain.append(('account_id', 'in', self.account_id.ids))

        caccount = self.env['account.move.line'].sudo().search(domain)

        for line in caccount.sorted(key=lambda x: x.move_id.date):
            debit = 0
            credit = 0
            current = 0
            distribution_names = []

            if self.currency_id.name == 'VES':
                debit += line.debit
                credit += line.credit
                
                current += line.debit
                current += line.credit

            elif self.currency_id.name == 'USD':
                debit += line.debit_usd
                credit += line.credit_usd
                
                current += line.debit_usd
                current += line.credit_usd

            if isinstance(line.analytic_distribution, str):
                analytic_distribution_list = json.loads(line.analytic_distribution)
            else:
                analytic_distribution_list = line.analytic_distribution

            if analytic_distribution_list:
                for distribution in analytic_distribution_list:
                    account = self.env['account.analytic.account'].browse(int(distribution))
                    if account.exists():
                        distribution_names.append(f'[{account[0].code}] {account[0].name}')

            values = {
                'date': line.move_id.date,
                'comp_number': line.move_id.name,
                'doc_num': line.move_id.invoice_number if line.move_id.invoice_number else line.move_id.supplier_invoice_number,
                'partner': line.partner_id.name,
                'description': line.name,
                'debit': debit,
                'credit': credit,
                'current': current,
                'account_id': line.account_id.id,
                'analytic_distribution': distribution_names,
            }
            results.append(values)

            # Crear diccionario con datos de las cuentas
            acc = {
                'id': line.account_id.id,
                'code': line.account_id.code,
                'name': line.account_id.name,
            }
            
            # Verificar que la cuenta no exista ya en accounts antes de agregarla
            if not any(account['id'] == acc['id'] for account in accounts):
                accounts.append(acc)

        if results == [] and accounts == []:
            raise UserError('Disculpe, no se encontraron registro en el rango de fecha seleccionado.')

        data = {
            'items': results,
            'accounts': accounts,
            'company': self.company_id.name,
            'ruc': self.company_id.vat,
            'currency_id': self.currency_id,
            'currency': self.currency_id.name,
            'date_now': self.date_now,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'previous_amount': self.previous_amount,
        }
        return data 


    # *******************  REPORTE EN EXCEL ****************************

    def generate_xls_report(self):
        wb1 = xlwt.Workbook(encoding='utf-8')
        ws1 = wb1.add_sheet(_('Libro Mayor de Análisis'))
        fp = BytesIO()
        items = self._prepare_data()

        number_format = xlwt.XFStyle()
        number_format.num_format_str = '#.##0,00'

        header_tittle_style = xlwt.easyxf("font: name Helvetica size 20 px, bold 1, height 170; align: horiz center, vert centre;")
        header_content_style = xlwt.easyxf("font: name Helvetica size 16 px, bold 1, height 170; align: horiz center, vert centre; pattern:pattern solid, fore_colour silver_ega;")
        lines_style_left = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: bottom thin; align: horiz left, vert centre;")
        lines_style_center = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: bottom thin; align: horiz center, vert centre;")
        lines_style_right = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: bottom thin; align: horiz right, vert centre;")
        
        table_style_center = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: left thin, right thin, top thin, bottom thin; align: horiz center, vert centre;")
        table_style_right = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: left thin, right thin, top thin, bottom thin; align: horiz right, vert centre;")

        row = 0
        col = 0
        ws1.row(row).height = 500

        #CABECERA DEL REPORTE
        ws1.write_merge(row,row, 0, 2, self.company_id.name, header_tittle_style)
        xdate = self.date_now.strftime('%d/%m/%Y %I:%M:%S %p')
        xdate = datetime.strptime(xdate,'%d/%m/%Y %I:%M:%S %p') - timedelta(hours=4)
        ws1.write_merge(row,row, 5, 7, xdate.strftime('%d/%m/%Y %I:%M:%S %p'), header_tittle_style)
        row += 1
        ws1.write_merge(row,row, 0, 2, 'R.I.F. ' + self.company_id.vat, header_tittle_style)
        row += 1
        ws1.write_merge(row,row, 0, 2, _("Libro Mayor de Análisis"), header_tittle_style)
        row += 1
        ws1.write_merge(row,row, 0, 2, _('Desde: ') + self.date_from.strftime('%d/%m/%Y') + _(' Hasta: ') + self.date_to.strftime('%d/%m/%Y'), header_tittle_style)
        row += 2
        


        for account in items['accounts']:
            #Cuenta Contable
            ws1.write(row,col+0, _("Código"),header_content_style)
            ws1.write_merge(row,row, 1, 2, _("Descripción de la Cuenta"),header_content_style)
            ws1.write(row,col+5, _("Saldo Anterior: "),header_tittle_style)
            ws1.write(row,col+6, self.float_format(self.previous_amount),header_tittle_style)
            # row += 1
            # ws1.write(row,col+0, account.group_id.code_prefix,lines_style_center)
            # ws1.write_merge(row,row, 1, 2, account.group_id.name,lines_style_center)
            row += 1

            ws1.write(row,col+0, account['code'],lines_style_center)
            ws1.write_merge(row,row, 1, 2, account['name'],lines_style_center)

            row += 2
    
            #CABECERA DE LA TABLA 
            ws1.write(row,col+0, _("Fecha Contable"),header_content_style)
            ws1.col(col+0).width = int((len('xx/xx/xxxx')+4)*256)
            ws1.write(row,col+1, _("Cuenta Analítica"),header_content_style)
            ws1.col(col+1).width = int((len('Cuenta Analítica')+18)*256)
            ws1.write(row,col+2, _("N° Comprobante"),header_content_style)
            ws1.col(col+2).width = int((len('N° Comprobante')+10)*256)
            # ws1.write(row,col+3, _("Tipo de Documento"),header_content_style)
            # ws1.col(col+3).width = int((len('Tipo de Documento')+10)*256)
            ws1.write(row,col+3, _("N° Documento"),header_content_style)
            ws1.col(col+3).width = int((len('N° Documento')+10)*256)
            ws1.write(row,col+4, _("Empresa/Cliente/Proveedor"),header_content_style)
            ws1.col(col+4).width = int((len('Empresa/Cliente/Proveedor')+20)*256)
            ws1.write(row,col+5, _("Descripción del Movimiento"),header_content_style)
            ws1.col(col+5).width = int((len('Descripción del Movimiento')+20)*256)
            ws1.write(row,col+6, _("Débitos"),header_content_style)
            ws1.col(col+6).width = int((len('xxx.xxx.xxx,xx xxx')+2)*256)
            ws1.write(row,col+7, _("Créditos"),header_content_style)
            ws1.col(col+7).width = int((len('xxx.xxx.xxx,xx xxx')+2)*256)
            ws1.write(row,col+8, _("Saldo Actual"),header_content_style)
            ws1.col(col+8).width = int((len('xxx.xxx.xxx,xx xxx')+2)*256)

            #VARIABLES TOTALES
            total_previous = 0
            total_debit = 0
            total_credit = 0
            total_current = 0

            #LINEAS
            for item in items['items']:
                if item['account_id'] == account['id']:
                    row += 1
                    # Fecha Contable
                    if item['date']:
                        ws1.write(row,col+0, item['date'].strftime('%d/%m/%Y'),lines_style_center)
                    else:
                        ws1.write(row,col+0, '',lines_style_center)
                    # Cuenta Analítica
                    if item['analytic_distribution']:
                        ws1.write(row,col+1, item['analytic_distribution'],lines_style_left)
                    else:
                        ws1.write(row,col+1, '',lines_style_left)
                    # N° Comprobante
                    if item['comp_number']:
                        ws1.write(row,col+2, item['comp_number'],lines_style_left)
                    else:
                        ws1.write(row,col+2, '',lines_style_left)
                    # Tipo de Documento
                    # if item.doc_type:
                    #     ws1.write(row,col+3, dict(item._fields['doc_type'].selection).get(item.doc_type),lines_style_left)
                    # else:
                    #     ws1.write(row,col+3, '',lines_style_left)
                    # N° Documento
                    if item['doc_num']:
                        ws1.write(row,col+3, item['doc_num'],lines_style_left)
                    else:
                        ws1.write(row,col+3, '',lines_style_left)
                    # Empresa/Cliente/Proveedor
                    if item['partner']:
                        ws1.write(row,col+4, item['partner'],lines_style_left)
                    else:
                        ws1.write(row,col+4, '',lines_style_left)
                    # Descripción del Movimiento
                    if item['description']:
                        ws1.write(row,col+5, item['description'],lines_style_left)
                    else:
                        ws1.write(row,col+5, '',lines_style_left)
                    # # Saldo Anterior
                    # ws1.write(row,col+4, self.float_format(item.previous),lines_style_right)
                    # Débitos
                    ws1.write(row,col+6, item['debit'],lines_style_right)
                    # Créditos
                    ws1.write(row,col+7, item['credit'],lines_style_right)
                    # Saldo Actual
                    ws1.write(row,col+8, item['current'],lines_style_right)

                    # total_previous += item.previous
                    total_debit += item['debit']
                    total_credit += item['credit']
                    # total_current += item.current

            #TOTALES
            row += 1
            ws1.write_merge(row,row,col+0,col+5, _('Total general'),lines_style_right)
            # ws1.write(row,col+4, self.float_format(total_previous), lines_style_right)
            ws1.write(row,col+6, total_debit, lines_style_right)
            ws1.write(row,col+7, total_credit, lines_style_right)
            ws1.write(row,col+8, '', lines_style_right)
            row += 2

        #IMPRESIÓN
        wb1.save(fp)
        
        out = base64.encodebytes(fp.getvalue()).decode('utf-8')
        fecha  = datetime.now().strftime('%d/%m/%Y') 
        self.write({'state': 'get', 'report': out, 'name': _('Libro Mayor de Análisis ')+ fecha +'.xls'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.analysis.ledger',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }