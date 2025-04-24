# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HRPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    @api.depends('name', 'total_usd', 'salary_rule_id')
    def _compute_dias(self):
        for rec in self:
            valor_dias = ""
            valor_horas = ""
            worked_days_line_ids = rec.slip_id.worked_days_line_ids

            if rec.struct_id.hr_payment_type == 'vacation':
                dia_adicional_vaca = rec.slip_id.dia_adicional_vaca
                dia_adicional_bono = rec.slip_id.dia_adicional_bono
                if rec.salary_rule_id.code in ['DVA','DBVA']:
                    vaca_days = worked_days_line_ids.filtered(lambda x: x.code == 'VACA')
                    valor_dias = 15 if vaca_days else ""
                elif rec.salary_rule_id.code in ['DDFVACA','FERI']:
                    work_days = worked_days_line_ids.filtered(lambda x: x.code in ['DDFVACA','FERI'])
                    num = 0
                    for work_day in work_days:
                        num += work_day.number_of_days
                    valor_dias = num if work_days else ""
                elif rec.salary_rule_id.code == 'DAVA':
                    valor_dias = dia_adicional_vaca if dia_adicional_vaca else ""
                elif rec.salary_rule_id.code == 'DABA':
                    valor_dias = dia_adicional_bono if dia_adicional_bono else ""
            elif rec.struct_id.hr_payment_type == 'cesta_ticket':
                if rec.salary_rule_id.code == 'CESTIK':
                    total_dias = 30
                    if rec.slip_id.contract_id.date_start > rec.slip_id.date_from and rec.slip_id.contract_id.date_start < rec.slip_id.date_to:
                        dias = rec.slip_id.contract_id.date_start.day - 1
                        total_dias = 30 - dias
                    valor_dias = total_dias
            else:
                if rec.struct_id.hr_payment_type != 'commision':
                    if rec.category_id.code == 'BASIC':
                        extras = 0
                        if rec.slip_id.date_to.day > 15 and rec.slip_id.date_to.day < 30:
                            #si se cumple esta condicion debo contar los dias desde el date_to.day hasta el 30
                            if worked_days_line_ids.filtered(lambda x: x.code == 'WORK100'):
                                extras = 30 - rec.slip_id.date_to.day
                        valor_dias = worked_days_line_ids.filtered(lambda x: x.code == 'WORK100').number_of_days + extras
                    elif rec.salary_rule_id.code == 'DSP':
                        if rec.slip_id.dias_pendientes > 0:
                            valor_dias = round(rec.slip_id.dias_pendientes,2)
                        else:
                            valor_dias = ""
                    else:
                        worked_days_line_ids = rec.slip_id.worked_days_line_ids.filtered(lambda x: x.code == rec.code)
                        if not worked_days_line_ids:
                            worked_days_line_ids = rec.slip_id.worked_days_line_ids.filtered(lambda x: x.code == '%sT' % rec.code)
                        if rec.salary_rule_id.mostrar_cantidad == 'dias':
                            if len(worked_days_line_ids) > 0:
                                valor_dias = round(worked_days_line_ids.number_of_days,2)
                            else:
                                valor_dias = ""
                            valor_horas = ""
                        elif rec.salary_rule_id.mostrar_cantidad == 'horas':
                            if len(worked_days_line_ids) > 0:
                                valor_horas = round(worked_days_line_ids.number_of_hours,2)
                            else:
                                valor_horas = ""
                            valor_dias = ""
                        else:
                            valor_dias = ""
                            valor_horas = ""
                else:
                    if rec.salary_rule_id.code == 'CDH':
                        fecha_inicio = rec.slip_id.date_from
                        fecha_fin = rec.slip_id.date_to
                        # dias = (fecha_fin - fecha_inicio).days + 1
                        total_dias = 30
                        if rec.slip_id.contract_id.date_start > rec.slip_id.date_from and rec.slip_id.contract_id.date_start < rec.slip_id.date_to:
                            dias = rec.slip_id.contract_id.date_start.day - 1
                            total_dias = 30 - dias
                        valor_dias = total_dias - (rec.slip_id.sabados_periodo + rec.slip_id.domingos_periodo + rec.slip_id.feriados_periodo)
                    if rec.salary_rule_id.code == 'DDESS':
                        valor_dias = rec.slip_id.sabados_periodo
                    if rec.salary_rule_id.code == 'DDESD':
                        valor_dias = rec.slip_id.domingos_periodo
                    if rec.salary_rule_id.code == 'FERI':
                        valor_dias = rec.slip_id.feriados_periodo

            rec.dias = str(valor_dias)
            rec.horas = str(valor_horas)

