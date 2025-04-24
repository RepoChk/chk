# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "gc_employee_loan",
    'version': '0.1',
    'category' : 'Payroll',
    'summary': """Prestamos para empleados""",
    'author': 'Grupo Chakao',
    'company': 'Grupo Chakao',
    'maintainer': 'Grupo Chakao',
    'website': 'neumaticoschakao@gmail.com',
    'description': "Este addon contiene complementos para el modulo de prestamos",
    'images' : [],
    'depends' : [
        'l10n_ve_payroll',
        'hr_payroll',
        'gchakao_custom',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/rule.xml',
        'views/hr_employee_loan.xml',
        'views/hr_employee_loan_installment_line.xml',
        'views/hr_payslip.xml',
        'views/hr_payment_order.xml',
        'views/type_loan.xml',
        'wizard/pay_fee.xml',
    ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

