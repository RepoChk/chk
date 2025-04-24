from odoo import api, models

class WebDraftInvoiceRibbon(models.AbstractModel):
    _name = "web.draft.invoice.ribbon"
    _description = "Web Draft Invoice Ribbon"

    @api.model
    def get_draft_invoice_status(self):
        """
        Devuelve si hay facturas en estado borrador para la compañía actual.
        """
        company_id = self.env.company.id
        draft_count = self.env['account.move'].search_count([
            ('state', '=', 'draft'),
            ('move_type', '=', 'out_invoice'),
            ('company_id', '=', company_id),
        ])

        return {
            'show_ribbon': draft_count > 0,  # Se muestra solo si hay facturas en borrador
            'company_id': company_id,
            'qty': draft_count,
        }
