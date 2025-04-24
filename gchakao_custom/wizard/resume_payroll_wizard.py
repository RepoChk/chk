from datetime import datetime, timedelta
from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError
import io
from io import BytesIO

import xlsxwriter
import shutil
import base64
import csv
import xlwt

class ResumePayrollWizard(models.TransientModel):
    _name = 'resume.payroll.wizard'
    _description = "Resumen de Nómina"

    date_from  = fields.Date('Desde', required=True,)
    date_to = fields.Date(string='Hasta', required=True,)

    date = fields.Datetime(string="Fecha", default=fields.Datetime.now)
    run_ids = fields.Many2many('hr.payslip.run', compute='_compute_run_ids')
    payslip_run_ids = fields.Many2many('hr.payslip.run', domain="[('id', 'in', run_ids), ]", required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id.id)
    currency_id_dif = fields.Many2one('res.currency', related='company_id.currency_id_dif')

    #excel
    report = fields.Binary('Archivo listo', filters='.xls', readonly=True)
    name = fields.Char('Nombre del archivo', size=32)
    state = fields.Selection([('choose', 'choose'), ('get', 'get')], default='choose')

    @api.depends('date_from','date_to')
    def _compute_run_ids(self):
        domain = [
            ('company_id', '=', self.company_id.id),
            # ('state', 'in', ['close','paid'])
        ]
        if self.date_from:
            domain.append(('date_start', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_end', '<=', self.date_to))
        self.run_ids = self.env['hr.payslip.run'].search(domain).ids

    def _get_report_name(self):
        return f'Período desde {self.date_from.strftime("%d-%m-%Y")} hasta {self.date_to.strftime("%d-%m-%Y")}'

    def prepare_report_data(self):
        result = []
        for slip in self.payslip_run_ids.mapped('slip_ids').sorted(lambda i: i.payslip_run_id.id, reverse=True).sorted(lambda reg: (reg.payslip_run_id.id, reg.employee_id.name), reverse=False):
            total_descuentos_usd = 0
            total_descuentos_bs = 0
            if len(slip.installment_ids) >= 1:
                total_descuentos_usd += slip.installment_amount
            if slip.add_discount:
                total_descuentos_usd += sum(slip.discount_ids.mapped('amount_usd'))
            total_descuentos_bs = total_descuentos_usd * slip.tasa_cambio
            values = {
                'employee_name': slip.employee_id.name.upper(),
                'employee_cdi': slip.employee_id.identification_id,
                'bank_account_id': slip.employee_id.sudo().bank_account_id.acc_number,
                'department_name': slip.contract_id.department_id.name.upper(),
                'department_id': slip.contract_id.department_id.id,
                'wage': slip.contract_id.wage,
                'payslip_run_name': slip.payslip_run_id.name.upper(),
                'payslip_run_id': slip.payslip_run_id.id,
                'payslip_id': slip.number,
                'currency_id': slip.company_id.currency_id.id,
                'total_nomina': sum(slip.line_ids.filtered(lambda rule: rule.category_id.code == 'NET').mapped('total')),
                'total_cestaticket': 0,
                'total_hc': sum(slip.line_ids.filtered(lambda rule: rule.code == 'DPLZ').mapped('total')) / slip.tasa_cambio if sum(slip.line_ids.filtered(lambda rule: rule.code == 'DPLZ').mapped('total')) > 0 else 0,
                'total_prestamo_desc': total_descuentos_usd,
                'total_prestamo': total_descuentos_bs,
                'job_name': slip.job_id.name.upper(),
                'run_date_start': slip.date_from,
                'run_date_end': slip.date_to,
            }
            
            # Añadir el registro si no es cesta_ticket
            if slip.struct_id.hr_payment_type != 'cesta_ticket':
                result.append(values)
            else:
                # Unir la nómina de cestaticket con la segunda quincena
                for res in result:
                    if res['employee_cdi'] == slip.employee_id.identification_id and res['run_date_end'].day >= 16:
                        res['total_cestaticket'] += sum(slip.line_ids.filtered(lambda rule: rule.category_id.code == 'NET').mapped('total'))
        
        data = {
            'name': self._get_report_name(),
            'form': result,
        }
        return data

    def print_report_data(self):
        data = self.prepare_report_data()
        return self.env.ref('gchakao_custom.action_report_resume_payroll').report_action([], data=data)
    
   
    # def print_report_xls(self):
    #     if not self.payslip_run_id:
    #         raise UserError('No hay nominas seleccionadas para imprimir')

    #     wb1 = xlwt.Workbook(encoding='utf-8')
    #     ws1 = wb1.add_sheet('Resumen')
    #     fp = BytesIO()

    #     date_format = xlwt.XFStyle()
    #     date_format.num_format_str = 'dd/mm/yyyy'

    #     number_format = xlwt.XFStyle()
    #     number_format.num_format_str = '#,##0.00'

    #     sub_header_style = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: left thin, right thin, top thin, bottom thin;")
    #     sub_header_style_c = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: left thin, right thin, top thin, bottom thin; align: horiz center")
    #     sub_header_style_l = xlwt.easyxf("font: name Helvetica size 10 px, bold 1, height 170; borders: left thin, right thin, top thin, bottom thin; align: horiz left")
    #     header_style_c = xlwt.easyxf("font: name Helvetica size 10 px, height 170; align: horiz center")

    #     row = 0
    #     col = 0
    #     ws1.row(row).height = 500

    #     ################ Cuerpo del excel ################

    #     ws1.write_merge(row,row, 1, 3, "Razón Social:"+" "+str(self.company_id.name), sub_header_style)
    #     row += 1
    #     ws1.write_merge(row, row, 1, 3,"Rif:"+" "+str(self.company_id.partner_id.vat), sub_header_style)
    #     row += 1
    #     ws1.write_merge(row,row, 1, 3, "Resumen de nomina",sub_header_style_c)
    #     row += 1
    #     ws1.write_merge(row,row, 1, 1, "Fecha",sub_header_style_c)
    #     ws1.write_merge(row,row, 2, 2, self.date, date_format)
    #     row += 1
    #     department_id_ids = [dep.department_id_id.id for dep in self.payslip_run_id.mapped('slip_ids.employee_id')]
    #     department_id_ids = list(set(department_id_ids))
    #     asig_total_g = 0
    #     ded_total_g = 0
    #     for lot in self.payslip_run_id:
    #         row += 1
    #         ws1.write_merge(row, row, 1, 5, lot.name, sub_header_style_c)
    #         row += 1
    #         for dep in department_id_ids:
    #             resumen = []
    #             department_id = ''
    #             for slip in lot.slip_ids:
    #                 if slip.employee_id.department_id_id.id == dep:
    #                     department_id = slip.employee_id.department_id_id.name
    #                     for line in slip.line_ids.filtered(lambda l: l.code not in ('GROSS','NET')):
    #                         values = {
    #                             'name': line.name,
    #                             'asig': sum(slip.line_ids.filtered(lambda l: l.category_id.code in ('ALW','BASIC') and line.id == l.id).mapped('amount')),
    #                             'ded': sum(slip.line_ids.filtered(lambda l: l.category_id.code == 'DED' and line.id == l.id).mapped('amount')),
    #                             'dep': dep,
    #                         }
    #                         if not any(res['name'] == line.name and res['dep'] == dep for res in resumen):
    #                             resumen.append(values)
    #                         else:
    #                             for res in resumen:
    #                                 if res['name'] == line.name and res['dep'] == dep:
    #                                     res['asig'] += values['asig']
    #                                     res['ded'] += values['ded']
    #             if department_id == '':
    #                 continue

    #             row += 1
    #             ws1.write_merge(row, row, 1, 5, 'DEPARTAMENTO: '+ department_id, header_style_c)
    #             row += 1
    #             ws1.write_merge(row, row, 1, 2, 'CONCEPTO', sub_header_style_l)
    #             ws1.write_merge(row, row, 3, 3, 'ASIGNACIONES', sub_header_style_c)
    #             ws1.write_merge(row, row, 4, 4, 'DEDUCCIONES', sub_header_style_c)
    #             ws1.write_merge(row, row, 5, 5, 'NETO', sub_header_style_c)
    #             asig_total = 0
    #             ded_total = 0
    #             for res in resumen:
    #                 if dep and dep == res['dep']:
    #                     row += 1
    #                     ws1.write_merge(row, row, 1, 2, res['name'], sub_header_style)
    #                     ws1.write_merge(row, row, 3, 3, res['asig'], number_format)
    #                     ws1.write_merge(row, row, 4, 4, res['ded'], number_format)
    #                     asig_total += res['asig']
    #                     ded_total += res['ded']
    #                     asig_total_g += res['asig']
    #                     ded_total_g += res['ded']
    #             row += 1
    #             ws1.write_merge(row, row, 3, 3, asig_total, number_format)
    #             ws1.write_merge(row, row, 4, 4, ded_total, number_format)
    #             ws1.write_merge(row, row, 5, 5, (asig_total-ded_total), number_format)
    #             row += 1
    #         row += 1

    #     ws1.write_merge(8, 8, 7, 8, 'TOTAL GENERAL', sub_header_style_c)
    #     ws1.write_merge(9, 9, 7, 7, 'ASIGNACIONES', sub_header_style_l)
    #     ws1.write_merge(10, 10, 7, 7, 'DEDUCCIONES', sub_header_style_l)
    #     ws1.write_merge(11, 11, 7, 7, 'NETO', sub_header_style_l)
    #     ws1.write_merge(9, 9, 8, 8, asig_total_g, number_format)
    #     ws1.write_merge(10, 10, 8, 8, ded_total_g, number_format)
    #     ws1.write_merge(11, 11, 8, 8, (asig_total_g-ded_total_g), number_format)
        
    #     wb1.save(fp)
    #     out = base64.b64encode(fp.getvalue())
    #     date  = datetime.now().strftime('%d/%m/%Y')
    #     self.write({'state': 'get', 'report': out, 'name':'Resumen de nomina.xls'})
        
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'pre.payroll.wizard',
    #         'view_mode': 'form',
    #         'view_type': 'form',
    #         'res_id': self.id,
    #         'views': [(False, 'form')],
    #         'target': 'new',
    #     }