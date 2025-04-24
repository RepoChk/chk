# coding: utf-8
from collections import defaultdict
from markupsafe import Markup
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import formatLang
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
import calendar
from babel.numbers import format_currency
from odoo.tools import float_compare, float_is_zero, plaintext2html

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    struct_code = fields.Char(
        string='Código',
        related='struct_type_id.code',
    )

    discount_ids = fields.One2many(
        'hr.discount',
        'payslip_id',
        string='Descuentos',
    )

    discount_total_usd = fields.Monetary(string='Monto USD', currency_field='currency_id_dif', compute='_discount_total')
    discount_total_bs = fields.Monetary(string='Monto', currency_field='currency_id', compute='_discount_total')

    add_discount = fields.Boolean(
        string='Usar Descuentos', 
    )

    is_confidential = fields.Boolean(string='Confidencial', related='struct_id.confidential', store=True)

    date_from_vacation = fields.Date(string='Inicio de Vacaciones', readonly=True,)
    date_to_vacation = fields.Date(string='Fin de Vacaciones', readonly=True,)
    date_return_vacation = fields.Date(string='Retorno de Vacaciones', readonly=True,)
    
    period_to_vacation = fields.Char(string='P. Vacaciones', compute='_compute_period_to_vacation', store=True, help='Periodo de Vacaciones', )
    por_discount_pp = fields.Float(compute='_compupe_por_discount_pp',)
    vacation_days = fields.Float(string='Días de Vacaciones',)

    dia_adicional_vaca = fields.Integer(
        string='D/A Vacaciones',
        compute='_compute_dias_adicionales',
        store=True,
        help='Día adicional de vacaciones', 
    )

    dia_adicional_bono = fields.Integer(
        string='D/A de Bono',
        compute='_compute_dias_adicionales',
        store=True,
        help='Día adicional de bono'
    )

    antiguedad_pagar = fields.Integer(
        string='Antig. Cancelar',
        compute='_compute_dias_adicionales',
        store=True,
        help='Antiguedad a Cancelar', 
    )
 
    @api.depends('contract_id','employee_id','add_discount')
    def _compupe_por_discount_pp(self):
        for rec in self:
            rec.por_discount_pp = rec.contract_id.company_id.por_discount_pp / 100 if rec.contract_id.company_id.por_discount_pp > 0 else 0.01

    payment_order_id = fields.Many2one(
        'hr.payment.order',
        string='Orden de Pago',
        readonly=True,
    )

    anio_from = fields.Selection(
        selection='_get_years',
        string='Inicio',
        default=lambda self: str(fields.Date.today().year)
    )

    anio_to = fields.Selection(
        selection='_get_years',
        string='Fin',
        default=lambda self: str(fields.Date.today().year)
    )

    discount_status = fields.Selection([
        ('sin_descuentos', 'Sin Descuentos'),
        ('bueno', 'Bueno'),
        ('excedido', 'Excedido')],
        string='Estatus de Descuentos', 
        compute='_compute_discount_status', 
        store=True, 
        default='sin_descuentos',
    )

    warning_message_status = fields.Char(compute='_compute_warning_message_status', store=True, readonly=True)

    sabados_periodo = fields.Integer(string='Sábados', compute='_calcular_sabados_periodo', store=True)
    domingos_periodo = fields.Integer(string='Domingos', compute='_calcular_domingos_periodo', store=True)
    feriados_periodo = fields.Integer(string='Feriados', compute='_calcular_feriados_periodo', store=True)
    dias_pendientes = fields.Float(string='Dias pendientes por pagar', default=0.0)

    @api.depends('date_to', 'date_from')
    def _calcular_sabados_periodo(self):
        for record in self:
            contador = 0
            for i in range((record.date_to - record.date_from).days + 1):
                if (record.date_from + timedelta(days=i)).weekday() == 5:
                    contador += 1
            record.sabados_periodo = contador

    @api.depends('date_to', 'date_from')
    def _calcular_domingos_periodo(self):
        for record in self:
            contador = 0
            for i in range((record.date_to - record.date_from).days + 1):
                if (record.date_from + timedelta(days=i)).weekday() == 6:
                    contador += 1
            record.domingos_periodo = contador

    @api.depends('date_to', 'date_from')
    def _calcular_feriados_periodo(self):
        for record in self:
            feriados = self.env['resource.calendar.leaves'].search_count([
                ('date_from', '>=', record.date_from),
                ('date_to', '<=', record.date_to),
                ('holiday_id', '=', False),
                ('company_id', '=', record.company_id.id),
                ('work_entry_type_id.code', '=', 'FERI'),
            ])
            record.feriados_periodo = feriados or 0

    def _get_years(self):
        current_year = fields.Date.today().year
        years = [(str(year), str(year)) for year in range(2019, current_year + 1)]
        return years
    
    @api.depends('discount_ids')
    def _discount_total(self):
        for rec in self:
            rec.discount_total_usd = 0
            rec.discount_total_bs = 0
            if len(rec.discount_ids) > 0:
                rec.discount_total_usd = sum(rec.discount_ids.mapped('amount_usd')) or 0
                rec.discount_total_bs = sum(rec.discount_ids.mapped('amount_bs')) or 0

    @api.onchange('discount_ids')
    def _onchange_discount_ids(self):
        porc = self.por_discount_pp
        for rec in self:
            total = sum(rec.line_ids.filtered(lambda line: line.category_id.code in ('BASIC', 'ASIGNA', 'SUBS', 'BONO')).mapped('total'))
            if len(rec.discount_ids) > 0:
                discount = sum(rec.discount_ids.mapped('amount_bs'))

    @api.depends('struct_id','employee_id','struct_code')
    def _compute_period_vacation(self):
        for rec in self:
            rec.date_from_vacation = False
            rec.date_to_vacation = False
            rec.date_return_vacation = False
            if rec.struct_id.type_id.code == 'VACA':
                hr_leave = self.env['hr.leave'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', '=', 'validate'),
                    ('date_from', '>=', rec.date_from),
                    ('date_to', '<=', rec.date_to)
                ], order='date_from')

                if hr_leave:
                    rec.date_from_vacation = hr_leave[0].date_from
                    rec.date_to_vacation = hr_leave[-1].date_to
                    # Calculamos la fecha de regreso de vacaciones
                    return_date = hr_leave[-1].date_to + timedelta(days=1)
                    # Aca ajustamos si cae en fin de semana o feriado
                    while return_date.weekday() in (5, 6) or self._is_holiday(return_date):
                        return_date += timedelta(days=1)
                    rec.date_return_vacation = return_date

    @api.depends('anio_from','anio_to')
    def _compute_period_to_vacation(self):
        for rec in self:
            rec.period_to_vacation = False
            if rec.anio_from and rec.anio_to:
                anio_from = rec.anio_from
                anio_to = rec.anio_to
                rec.period_to_vacation = f'{anio_from}-{anio_to}'

    def _is_holiday(self, date):
        holiday_count = self.env['resource.calendar.leaves'].search_count([
            ('date_from', '<=', date),
            ('date_to', '>=', date)
        ])
        return holiday_count > 0

    def payment_vals(self):
        self.ensure_one()
        return {
            'employee_id': self.employee_id.id,
            'payslip_id': self.id,
            'state': 'draft',
            'type_payment_order': 'payslip',
            'payslip_run_id':self.payslip_run_id.id,
            'company_id': self.company_id.id,
            'rate': self.tasa_cambio,
            'amount_usd': sum(self.line_ids.filtered(lambda x: x.category_id.code == 'NET').mapped('total_usd')),
            'amount_bs': sum(self.line_ids.filtered(lambda x: x.category_id.code == 'NET').mapped('total')),
        }

    def action_create_payment_order(self):
        payment_order = self.env['hr.payment.order'].create(self.payment_vals())
        for rec in self:
            rec.payment_order_id = payment_order.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payment.order',
            'res_id': payment_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('employee_id.contract_id','anio_to')
    def _compute_dias_adicionales(self):
        for rec in self:
            if not rec.employee_id or not rec.employee_id.contract_id:
                return 0

            fecha_inicio = rec.employee_id.contract_id.date_start
            anio_inicio = fecha_inicio.year

            anio_calculo = int(rec.anio_to)

            if not anio_inicio or not anio_calculo:
                return 0

            años_servicio = anio_calculo - anio_inicio

            # Calcular días adicionales para vacaciones y bono
            dia_adicional_vaca = min(max(años_servicio - 1, 0), 15)
            dia_adicional_bono = min(años_servicio, 15)

            rec.dia_adicional_vaca = dia_adicional_vaca
            rec.dia_adicional_bono = dia_adicional_bono
            rec.antiguedad_pagar = años_servicio

    @api.depends('date_from_vacation', 'date_to_vacation')
    def _compute_vacation_days(self):
        for payslip in self:
            if payslip.date_from_vacation and payslip.date_to_vacation:
                start_date = datetime.strptime(str(payslip.date_from_vacation), '%Y-%m-%d').date()
                end_date = datetime.strptime(str(payslip.date_to_vacation), '%Y-%m-%d').date()
                payslip.vacation_days = (end_date - start_date).days + 1
            else:
                payslip.vacation_days = 0

    def action_payslip_done(self):
        res = super(HrPayslip, self).action_payslip_done()
        for rec in self:
            #procesar prestaciones
            if rec.struct_id.procesar_prestaciones:
                rec.procesar_prestaciones()

            #procesar vacaciones historico
            if rec.struct_id.type_id.id == self.env.ref('l10n_ve_payroll.structure_type_vacaciones_anual').id:
                #busco el historico de vacaciones en el empleado, hr_employee_vacaciones
                vacaciones = self.env['hr.employee.vacaciones'].search([('employee_id', '=', rec.employee_id.id),
                                                                         ('anio', '=', rec.date_from.year)])
                dias_vaca = rec.worked_days_line_ids.filtered(lambda x: x.code == 'VACA')
                if vacaciones:
                    if dias_vaca:
                        vacaciones.dias_vaca += rec.vacation_days
                else:
                    if dias_vaca:
                        data = {
                            'employee_id': rec.employee_id.id,
                            'anio': int(rec.anio_from),
                            'dias_vaca': rec.vacation_days,
                            'company_id': rec.company_id.id,
                        }
                        self.env['hr.employee.vacaciones'].create(data)

            #procesar cuotas de prestamos
            if rec.installment_ids:
                for installment in rec.installment_ids:
                    if not installment.is_skip:
                        installment.is_paid = True
                    installment.payslip_id = rec.id
        return res

    @api.depends('date_to', 'date_from')
    def _calcular_lunes(self):
        contador = 0
        contadort = 0
        formato = "%d/%m/%Y"

        def contar_lunes(fecha_inicio, fecha_fin):
            # Inicializar contador de lunes
            contador_lunes = 0

            # Iterar por cada día entre las dos fechas
            while fecha_inicio <= fecha_fin:
                if fecha_inicio.weekday() == 0:  # 0 significa lunes
                    contador_lunes += 1
                fecha_inicio += timedelta(days=1)

            return contador_lunes

        for record in self:
            record.lunes_periodo = contar_lunes(record.date_from, record.date_to)

            adesde = record.date_from.year
            mdesde = record.date_from.month
            ddesde = 1  # self.date_from.day
            fechadesde = str(ddesde) + '/' + str(mdesde) + '/' + str(adesde)

            ahasta = record.date_to.year
            mhasta = record.date_to.month
            # dhasta=self.date_to.day
            monthRange = calendar.monthrange(ahasta, mhasta)
            dhasta = monthRange[1]

            fechahasta = str(dhasta) + '/' + str(mhasta) + '/' + str(ahasta)
            fechadesded = datetime.strptime(fechadesde, formato)
            fechahastad = datetime.strptime(fechahasta, formato)

            record.lunes_mes = contar_lunes(fechadesded, fechahastad)

        for record in self:
            dominio = [('employee_id', '=', record.employee_id.id),
                           ('date_start', '>=', record.date_from),
                           ('date_stop', '<=', record.date_to),]
            if record.struct_id.type_id.code != 'VACA':
                dominio.append(('work_entry_type_id.code', 'in', ['WORK100','FERI']))
            else:
                dominio.append(('work_entry_type_id.code', 'in', ['VACA','DDFVACA']))
            if record.employee_id and record.date_from and record.date_to:
                work_entries = record.env['hr.work.entry'].search(dominio)
                #de todas las work_entries agrupar por días
                dias = work_entries.mapped('date_start')
                #transformar a date from datetime
                dias = [d.date() for d in dias]
                dias = list(set(dias))
                #de esos días cuales son lunes
                contador_trabajado = 0
                for d in dias:
                    if d.weekday() == 0:
                        contador_trabajado += 1
                record.lunes_trabajados = contador_trabajado
            else:
                record.lunes_trabajados = 0


    @api.depends('discount_ids', 'line_ids')
    def _compute_discount_status(self):
        for payslip in self:
            if not payslip.discount_ids:
                payslip.discount_status = 'sin_descuentos'
            else:
                total_payslip_amount = sum(payslip.line_ids.filtered(lambda line: line.category_id.code in ('BASIC', 'ASIGNA', 'SUBS', 'BONO')).mapped('total'))
                total_discount_amount = sum(payslip.discount_ids.mapped('amount_usd')) * payslip.tasa_cambio
                por_discount_pp = payslip.por_discount_pp
                total = total_payslip_amount * por_discount_pp
                if total_discount_amount > total:
                    payslip.discount_status = 'excedido'
                else:
                    payslip.discount_status = 'bueno'

    @api.depends('discount_status', 'line_ids')
    def _compute_warning_message_status(self):
        for payslip in self:
            if payslip.discount_status == 'excedido':
                result = sum(payslip.line_ids.filtered(lambda line: line.category_id.code in ('BASIC', 'ASIGNA', 'SUBS', 'BONO')).mapped('total'))
                total = result * payslip.por_discount_pp
                formatted_result = format_currency(result, 'VES', locale='es_VE').replace('Bs.S', 'Bs. ')
                formatted_total = format_currency(total, 'VES', locale='es_VE').replace('Bs.S', 'Bs. ')
                payslip.warning_message_status = (
                    f"El total de los descuentos no debe superar el ({payslip.por_discount_pp * 100:.2f}%) de ({formatted_result}) que serían ({formatted_total})"
                )
            else:
                payslip.warning_message_status = False

    @api.model
    def compute_sheet(self):
        Leave = self.env['hr.leave']
        Discount = self.env['hr.discount']
        CalendarLeave = self.env['resource.calendar.leaves']
        self._calcular_feriados_periodo()
        
        for payslip in self:
            start_date = payslip.date_from
            end_date = payslip.date_to

            # Cálculo de descuentos
            discounts = Discount.search([
                ('employee_id', '=', payslip.employee_id.id),
                ('date_to', '>=', start_date),
                ('date_to', '<=', end_date),
                ('struct_id', '=', payslip.struct_id.id),
            ])
            payslip.write({'discount_ids': [(6, 0, discounts.ids)]})
            payslip.add_discount = bool(discounts)

            # Cálculo de vacaciones
            vacations = Leave.search([
                ('employee_id', '=', payslip.employee_id.id),
                ('request_date_from', '>=', start_date),
                ('request_date_to', '<=', end_date),
                ('state', '=', 'validate'),  # Solo vacaciones aprobadas
            ])

            if vacations:
                # Ordenar los registros de vacaciones por fecha
                vacations = vacations.sorted(key=lambda r: r.request_date_from)
                
                # Convertir las fechas a objetos datetime.date
                vacation_start_date = vacations[0].request_date_from
                vacation_end_date = vacations[-1].request_date_to
                
                # Tomar la fecha de inicio del primer registro y la fecha final del último registro
                payslip.date_from_vacation = vacation_start_date
                payslip.date_to_vacation = vacation_end_date
                
                # Calcular los días de vacaciones
                payslip.vacation_days = (vacation_end_date - vacation_start_date).days + 1
                
                # Determinar la fecha de retorno
                return_date = vacation_end_date + timedelta(days=1)
                
                # Obtener todos los días feriados
                holidays = CalendarLeave.search([
                    ('date_from', '>=', start_date),
                    ('date_to', '<=', end_date),
                    ('resource_id', '=', False)  # Solo días festivos generales
                ])
                holidays_dates = [
                    holiday.date_from.date() for holiday in holidays if holiday.date_from
                ]

                # Ajustar si la fecha de retorno cae en fin de semana o día feriado
                while return_date.weekday() in (5, 6) or return_date in holidays_dates:
                    return_date += timedelta(days=1)
                
                payslip.date_return_vacation = return_date

        res = super(HrPayslip, self).compute_sheet()
        return res

    # @api.model
    # def _prepare_line_values(self, line, account_id, date, debit, credit):
    #     line_values = super(HrPayslip, self)._prepare_line_values(line, account_id, date, debit, credit)
    #     account = self.env['account.account'].browse(account_id)
    #     if account.code.startswith(('1', '2')):
    #         line_values['analytic_distribution'] = {}
    #     return line_values

    def _remove_analytic_distribution(self, line_ids):
        for line in line_ids:
            account = self.env['account.account'].browse(line['account_id'])
            if account.code.startswith('1') or account.code.startswith('2'):
                line['analytic_distribution'] = {}
        return line_ids

    def _action_create_account_move(self):
        precision = self.env['decimal.precision'].precision_get('Payroll')

        # Add payslip without run
        payslips_to_post = self.filtered(lambda slip: not slip.payslip_run_id)

        # Adding pay slips from a batch and deleting pay slips with a batch that is not ready for validation.
        payslip_runs = (self - payslips_to_post).payslip_run_id
        for run in payslip_runs:
            if run._are_payslips_ready():
                payslips_to_post |= run.slip_ids

        # A payslip need to have a done state and not an accounting move.
        payslips_to_post = payslips_to_post.filtered(lambda slip: slip.state == 'done' and not slip.move_id)

        # Check that a journal exists on all the structures
        if any(not payslip.struct_id for payslip in payslips_to_post):
            raise ValidationError(_('One of the contract for these payslips has no structure type.'))
        if any(not structure.journal_id for structure in payslips_to_post.mapped('struct_id')):
            raise ValidationError(_('One of the payroll structures has no account journal defined on it.'))

        # Map all payslips by structure journal and pay slips month.
        # Case 1: Batch all the payslips together -> {'journal_id': {'month': slips}}
        # Case 2: Generate account move separately -> [{'journal_id': {'month': slip}}]
        if self.company_id.batch_payroll_move_lines:
            all_slip_mapped_data = defaultdict(lambda: defaultdict(lambda: self.env['hr.payslip']))
            for slip in payslips_to_post:
                all_slip_mapped_data[slip.struct_id.journal_id.id][slip.date or fields.Date().end_of(slip.date_to, 'month')] |= slip
            all_slip_mapped_data = [all_slip_mapped_data]
        else:
            all_slip_mapped_data = [{
                slip.struct_id.journal_id.id: {
                    slip.date or fields.Date().end_of(slip.date_to, 'month'): slip
                }
            } for slip in payslips_to_post]

        for slip_mapped_data in all_slip_mapped_data:
            for journal_id in slip_mapped_data: # For each journal_id.
                for slip_date in slip_mapped_data[journal_id]: # For each month.
                    fecha = slip_date if slip_mapped_data[journal_id][slip_date][0].struct_id.hr_payment_type != 'vacation' else slip_mapped_data[journal_id][slip_date][0].date_from
                    line_ids = []
                    debit_sum = 0.0
                    credit_sum = 0.0
                    date = fecha
                    move_dict = {
                        'narration': '',
                        'ref': fields.Date().end_of(fecha, 'month').strftime('%B %Y'),
                        'journal_id': journal_id,
                        'date': fecha,
                    }

                    for slip in slip_mapped_data[journal_id][slip_date]:
                        move_dict['narration'] += plaintext2html(slip.number or '' + ' - ' + slip.employee_id.name or '')
                        move_dict['narration'] += Markup('<br/>')
                        slip_lines = slip._prepare_slip_lines(date, line_ids)                        
                        line_ids.extend(slip_lines)
                    
                    line_ids = self._remove_analytic_distribution(line_ids)

                    for line_id in line_ids: # Get the debit and credit sum.
                        debit_sum += line_id['debit']
                        credit_sum += line_id['credit']

                    # The code below is called if there is an error in the balance between credit and debit sum.
                    if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                        slip._prepare_adjust_line(line_ids, 'credit', debit_sum, credit_sum, date)
                    elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                        slip._prepare_adjust_line(line_ids, 'debit', debit_sum, credit_sum, date)

                    # Add accounting lines in the move
                    move_dict['line_ids'] = [(0, 0, line_vals) for line_vals in line_ids]
                    move = self._create_account_move(move_dict)
                    for slip in slip_mapped_data[journal_id][slip_date]:
                        if slip.struct_id.hr_payment_type == 'vacation':
                            move.write({
                                'date': slip.date_from
                            })
                        slip.write({'move_id': move.id, 'date': date})
        return True