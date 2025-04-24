# Copyright 2022-2023 Sodexis
# License OPL-1 (See LICENSE file for full copyright and licensing details).

{
    "name": "Web Environment Ribbon Horizontal",
    "summary": """Mark a Test Environment with a red ribbon on the top in every page
        """,
    "version": "1.0.0",
    "category": "web",
    "author": "Editado por: Anderson Rodríguez",
    "license": "OPL-1",
    "installable": True,
    "application": False,
    "depends": [
        'gchakao_custom',
        'account',
        'l10n_ve_full',
        'account_dual_currency',
        'sale',
    ],
    "data": [
        "views/account_move_view.xml",
        "views/account_payment_view.xml",
        "views/account_journal_view.xml",
        "views/account_wh_islr_doc.xml",
        "views/account_wh_iva.xml",
        "views/sale_order_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "web_environment_ribbon_horizontal/static/src/components/*",
        ],
    },
}
