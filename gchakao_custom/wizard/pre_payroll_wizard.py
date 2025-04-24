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

class WizardReport_1(models.TransientModel):
    _name = 'pre.payroll.wizard'
    _description = "Reporte Resumen Nómina"

    date_from  = fields.Date('Desde', required=True,)
    date_to = fields.Date(string='Hasta', required=True,)

    date = fields.Datetime(string="Fecha", default=fields.Datetime.now)
    run_ids = fields.Many2many('hr.payslip.run', compute='_compute_run_ids')
    payslip_run_ids = fields.Many2many('hr.payslip.run', domain="[('id', 'in', run_ids), ]", required=True)
    department_ids = fields.Many2many('hr.department', domain="[('company_id','=', company_id), ]")
    type_report = fields.Selection([('detail', 'Detallado'),('resume', 'Resumido'),('analytic', 'Cuenta Analítica')], default='detail')
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

    def _get_department_ids(self):
        department_ids = []
        for run in self.payslip_run_ids.slip_ids.sorted(lambda i: i.contract_id.department_id.name, reverse=False):
            for department in run.contract_id.mapped('department_id'):
                if department.id not in department_ids:
                    department_ids.append(department.id)
        return department_ids

    def _get_analytic_account_ids(self):
        analytic_account_ids = []
        for run in self.payslip_run_ids.slip_ids.sorted(lambda i: i.contract_id.analytic_account_id.name, reverse=False):
            for department in run.contract_id.mapped('analytic_account_id'):
                if department.id not in analytic_account_ids:
                    analytic_account_ids.append(department.id)
        return analytic_account_ids

    def _get_report_name(self):
        return f'Período desde {self.date_from.strftime("%d-%m-%Y")} hasta {self.date_to.strftime("%d-%m-%Y")}'

    def _get_domain(self):
        domain = [
            ('company_id', '=', self.company_id.id),
            # ('state', 'in', ['done','paid']),
            ('payslip_run_id', 'in', self.payslip_run_ids.ids),
        ]
        if self.department_ids:
            domain.append(('contract_id.department_id', '=', self.department_ids.id))
        return domain

    def prepare_report_data_detailed(self):
        payslip_run = []
        for run in self.payslip_run_ids:
            run_id = {
                'id': run.id,
                'name': run.name,
                'slip_ids': [],
                'department_ids': [],
            }
            for slip in run.slip_ids.filtered(lambda l: l.contract_id.department_id.id in self.department_ids.ids \
                if self.department_ids else l.contract_id.department_id.id in self._get_department_ids()).sorted(lambda i: i.contract_id.department_id.name, reverse=False):
                res = {
                    'employee_name': slip.employee_id.name,
                    'employee_cdi': slip.employee_id.identification_id,
                    'bank_account_id': slip.employee_id.bank_account_id.acc_number,
                    'department_name': slip.contract_id.department_id.name,
                    'department_id': slip.contract_id.department_id.id,
                    'wage': slip.contract_id.wage,
                    'payslip_run_name': slip.payslip_run_id.name,
                    'payslip_run_id': slip.payslip_run_id.id,
                    'payslip_id': slip.number,
                    'hr_payment_type': slip.struct_id.hr_payment_type,
                    'currency_id': slip.company_id.currency_id.id,
                    'line_ids': [],
                    'vaca': 0,
                }
                run_id['slip_ids'].append(res)

                department = {
                    'id': slip.contract_id.department_id.id,
                    'name': slip.contract_id.department_id.name,
                }

                if not any(department['id'] == slip.contract_id.department_id.id for department in run_id['department_ids']):
                    run_id['department_ids'].append(department)

                total_asig = 0
                total_ded = 0
                total_apor = 0

                for line in slip.line_ids.filtered(lambda rule: rule.category_id.code not in ('GROSS','NET','NET_DED','NET_ASIG')):
                    asig = line.total if line.category_id.code in ('ALW','BASIC','SUBS','ASIGNA') else 0
                    ded = line.total if line.category_id.code == 'DED' else 0
                    apor = line.total if line.category_id.code == 'COMP' else 0

                    total_asig += asig
                    total_ded += ded

                    line_id = {
                        'name': line.name,
                        'dias': line.dias,
                        'code': line.category_id.code,
                        'asig': asig,
                        'ded': ded,
                        'apor': apor,
                    }
                    res['line_ids'].append(line_id)

                # Verifica si las asignaciones menos las deducciones es igual a 0
                res['vaca'] = 1 if (total_asig - total_ded) <= 0 else 0

            payslip_run.append(run_id)

        data = {
            'name': self._get_report_name(),
            'form': payslip_run,
        }

        return data

    def print_report_data_detailed(self):
        data = self.prepare_report_data_detailed()
        return self.env.ref('gchakao_custom.action_report_pre_payroll_detailed').report_action([], data=data)

    def prepare_report_data_summarized(self):
        payslip_run = []
        for run in self.payslip_run_ids: # lotes
            run_ids = {
                'id': run.id,
                'name': run.name,
                'line_ids': [],
                'department_ids': [],
            }
            payslip_ids = run.slip_ids.filtered(lambda l: l.contract_id.department_id.id in self.department_ids.ids \
                if self.department_ids else l.contract_id.department_id.id in self._get_department_ids()).sorted(lambda i: i.contract_id.department_id.id, reverse=False)
            
            for line in payslip_ids.line_ids.filtered(lambda rule: rule.category_id.code not in ('GROSS','NET','NET_DED','NET_ASIG','COMP')):
                line_id = {
                    'name':line.name,
                    'department_id':line.contract_id.department_id.id,
                    'department_name':line.contract_id.department_id.name,
                    'run_id': run.id,
                    'code':line.category_id.code,
                    'asig':line.total if line.category_id.code in ('ALW','BASIC','SUBS','ASIGNA') else 0,
                    'ded':line.total if line.category_id.code == 'DED' else 0,
                    'salary_rule_id': line.salary_rule_id.id,
                }

                department = {
                    'id': line.contract_id.department_id.id,
                    'name': line.contract_id.department_id.name,
                }

                if not any(department['id'] == line.contract_id.department_id.id for department in run_ids['department_ids']):
                    run_ids['department_ids'].append(department)

                if not any(slip_ids['salary_rule_id'] == line.salary_rule_id.id and slip_ids['department_id'] == line.contract_id.department_id.id for slip_ids in run_ids['line_ids']):
                    run_ids['line_ids'].append(line_id)
                else:
                    for res in run_ids['line_ids']:
                        if res['salary_rule_id'] == line.salary_rule_id.id and res['department_id'] == line.contract_id.department_id.id:
                            res['asig'] += line_id['asig']
                            res['ded'] += line_id['ded']
            payslip_run.append(run_ids)
        data = {
            'name': self._get_report_name(),
            'form': payslip_run,
        }

        return data    

    def print_report_data_summarized(self):
        data = self.prepare_report_data_summarized()
        return self.env.ref('gchakao_custom.action_report_pre_payroll_summarized').report_action([], data=data)

    def prepare_report_data_analytic(self):
        payslip_run = []
        missing_analytic_accounts = []

        for run in self.payslip_run_ids:  # lotes
            run_ids = {
                'id': run.id,
                'name': run.name,
                'line_ids': [],
                'analytic_account_ids': [],
            }
            
            for contract in run.slip_ids.mapped('contract_id'):
                if not contract.analytic_account_id:
                    missing_analytic_accounts.append({
                        'employee_name': contract.employee_id.name,
                        'contract_name': contract.name,
                    })

            if missing_analytic_accounts:
                missing_accounts_str = '\n'.join(
                    [f"{i+1}) {account['employee_name']}" for i, account in enumerate(missing_analytic_accounts)]
                )
                raise UserError(f"Los contratos de los siguientes empleados no tienen cuentas analíticas asignadas:\n{missing_accounts_str}")

            payslip_ids = run.slip_ids.filtered(
                lambda l: l.contract_id.analytic_account_id.id in self._get_analytic_account_ids()
            ).sorted(lambda i: i.contract_id.analytic_account_id.id, reverse=False)
            
            for line in payslip_ids.line_ids.filtered(lambda rule: rule.category_id.code not in ('GROSS', 'NET', 'NET_DED', 'NET_ASIG')):
                line_id = {
                    'name': line.name,
                    'analytic_account_id': line.contract_id.analytic_account_id.id,
                    'analytic_account_name': line.contract_id.analytic_account_id.name,
                    'run_id': run.id,
                    'code': line.category_id.code,
                    'asig': line.total if line.category_id.code in ('ALW', 'BASIC', 'SUBS', 'ASIGNA') else 0,
                    'ded': line.total if line.category_id.code == 'DED' else 0,
                    'apor': line.total if line.category_id.code == 'COMP' else 0,
                    'salary_rule_id': line.salary_rule_id.id,
                }
                
                analytic_account = {
                    'id': line.contract_id.analytic_account_id.id,
                    'name': line.contract_id.analytic_account_id.name,
                }

                if not any(analytic_account['id'] == line.contract_id.analytic_account_id.id for analytic_account in run_ids['analytic_account_ids']):
                    run_ids['analytic_account_ids'].append(analytic_account)
                
                if not any(slip_ids['salary_rule_id'] == line.salary_rule_id.id and slip_ids['analytic_account_id'] == line.contract_id.analytic_account_id.id for slip_ids in run_ids['line_ids']):
                    run_ids['line_ids'].append(line_id)
                else:
                    for res in run_ids['line_ids']:
                        if res['salary_rule_id'] == line.salary_rule_id.id and res['analytic_account_id'] == line.contract_id.analytic_account_id.id:
                            res['asig'] += line_id['asig']
                            res['ded'] += line_id['ded']
                            res['apor'] += line_id['apor']
            
            payslip_run.append(run_ids)
        
        data = {
            'name': self._get_report_name(),
            'form': payslip_run,
        }
        return data
        
    def print_report_data_analytic(self):
        data = self.prepare_report_data_analytic()
        return self.env.ref('gchakao_custom.action_report_pre_payroll_analytic').report_action([], data=data)
    
   
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