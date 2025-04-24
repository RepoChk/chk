from odoo import api, fields, models, _
from datetime import datetime, date
from odoo.exceptions import UserError, ValidationError

class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    mp_requisition_id = fields.Many2one(
        'material.purchase.requisition', 
        string='Requisición',
    )
    
    has_requisition_request = fields.Selection(
        related="category_id.has_requisition_request"
    )

    has_analytic_request = fields.Selection(
        related="category_id.has_analytic_request"
    )

    is_cxp = fields.Selection(
        related="category_id.is_cxp"
    )

    cxp_id = fields.Many2one(
        'material.purchase.requisition', 
        string='Pago directo CXP', 
    )

    department_manager_id = fields.Many2one(
        'res.users', 
        string='Gerente de Departamento',
        default=lambda self: self.env.context.get('mng_id'),
        readonly=True,
    )

    #Verificamos si existen usuarios requeridos y verificamos quien apruaba sea requerido. 
    # Si no hay usuarios requeridos, se aprueba automaticamente
    def approve_requisitions_cxp(self):
        for rec in self:
            if rec.is_cxp and rec.has_analytic_request:
                req_id = rec.cxp_id if rec.cxp_id else rec.mp_requisition_id
                approval_request = req_id.combined_approvals.filtered(lambda x: x.request_status == 'approved')
                if len(approval_request) == 2:
                    # Update the state of the related requisition to 'approved'
                    requisition = self.env['material.purchase.requisition'].browse(req_id.id)
                    requisition.state = 'approve'
                else:
                    pass
                rec.write({'date_confirmed': fields.Datetime.now()})

    def approve_requisitions(self):
        for rec in self:
            if rec.has_requisition_request and rec.has_analytic_request:
                approval_request = self.env['approval.request'].search([('request_status', '=', 'approved'),('mp_requisition_id', '=', rec.mp_requisition_id.id)])
                if len(approval_request) == 2:
                    # Update the state of the related requisition to 'approved'
                    requisition = self.env['material.purchase.requisition'].browse(rec.mp_requisition_id.id)
                    requisition.state = 'approve'
                else:
                    pass
                rec.write({'date_confirmed': fields.Datetime.now()})

    def action_approve(self, approver=None):
        res = super(ApprovalRequest, self).action_approve(approver)
        self.approve_requisitions()
        self.approve_requisitions_cxp()
        return res

    @api.depends('category_id', 'department_manager_id')
    def _compute_approver_ids(self):
        for request in self:
            users_to_approver = {}
            for approver in request.approver_ids:
                users_to_approver[approver.user_id.id] = approver

            users_to_category_approver = {}
            for approver in request.category_id.approver_ids:
                users_to_category_approver[approver.user_id.id] = approver

            approver_id_vals = []

            if request.category_id.manager_approval:
                manager = request.department_manager_id.id
                if not manager:
                    raise UserError(_('El departamento no tiene un gerente asignado.'))
                if manager:
                    manager_user_id = manager
                    manager_required = request.category_id.manager_approval == 'required'
                    # raise UserError(manager_required)
                    self._create_or_update_approver(manager_user_id, users_to_approver, approver_id_vals, manager_required, 9)
                    if manager_user_id in users_to_category_approver.keys():
                        users_to_category_approver.pop(manager_user_id)

            if request.category_id.is_amount:
                amount_currency_total = request.cxp_id.amount_currency_total
                if amount_currency_total > request.category_id.amount:
                    # high_payment_approvers = {user_id: approver for user_id, approver in users_to_category_approver.items()
                    #                         if approver.is_high_payment_approver}
                    # for user_id in high_payment_approvers:
                    #     self._create_or_update_approver(user_id, users_to_approver, approver_id_vals,
                    #                                     True,
                    #                                     high_payment_approvers[user_id].sequence)
                    limited_approvers = {user_id: approver for user_id, approver in users_to_category_approver.items()
                                     if not approver.is_limited_by_amount 
                                    #  and not approver.is_high_payment_approver
                                     }
                    for user_id in limited_approvers:
                        self._create_or_update_approver(user_id, users_to_approver, approver_id_vals,
                                                        limited_approvers[user_id].required,
                                                        limited_approvers[user_id].sequence)
                else:
                    for user_id in users_to_category_approver:
                        self._create_or_update_approver(user_id, users_to_approver, approver_id_vals,
                                                        users_to_category_approver[user_id].required,
                                                        users_to_category_approver[user_id].sequence)
            else:
                for user_id in users_to_category_approver:
                    self._create_or_update_approver(user_id, users_to_approver, approver_id_vals,
                                                    users_to_category_approver[user_id].required,
                                                    users_to_category_approver[user_id].sequence)

            for current_approver in users_to_approver.values():
                self._update_approver_vals(approver_id_vals, current_approver, False, 1000)

            request.update({'approver_ids': approver_id_vals})
