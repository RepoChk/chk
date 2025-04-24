# -*- coding: utf-8 -*-
{
    'name': "Venezuela: Gestion de Anticipos",

    'summary': """
       Anticipos de Clientes y proveedores en Venezuela
       """,
    'description': """
        Anticipos de Clientes y proveedores en Venezuela

    """,
    'author': 'José Luis Vizcaya López',
    'company': 'José Luis Vizcaya López',
    'maintainer': 'José Luis Vizcaya López',
    'website': 'https://vizcaya.mi-erp.app',
    'category': 'Localization',
    'depends': ['base', 'l10n_ve', 'contacts', 'account','account_accountant','account_dual_currency'],
    'data': [
        'views/account_payment.xml',
        'views/res_partner.xml',
    ],
    "license": "GPL-2",
    "price": 500,
    "currency": "USD",
}
