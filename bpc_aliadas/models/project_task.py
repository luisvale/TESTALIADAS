# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from collections import defaultdict
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    is_maintenance = fields.Boolean(related='helpdesk_ticket_id.is_maintenance')
    sale_team_id = fields.Many2one('crm.team', related='helpdesk_ticket_id.sale_team_id')

    def action_fsm_validate(self):
        self.restriction_maintenance()
        super(ProjectTask, self).action_fsm_validate()

    def restriction_maintenance(self):
        files = self.env['ir.attachment'].sudo().search([('res_model', '=', 'project.task'),
                                                         ('res_id', 'in', self.ids),
                                                         ('company_id', '=', self.env.company.id)])
        if not files:
            raise ValidationError(_("Esta tarea debe contener al menos un archivo adjunto."))

    def action_fsm_create_quotation(self):
        view_form_id = self.env.ref('sale.view_order_form').id
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations")
        action.update({
            'views': [(view_form_id, 'form')],
            'view_mode': 'form',
            'name': self.name,
            'context': {
                'fsm_mode': True,
                'form_view_initial_mode': 'edit',
                'default_partner_id': self.partner_id.id,
                'default_task_id': self.id,
                'default_company_id': self.company_id.id,
                'default_from_maintenance': self.is_maintenance,
                'default_team_id': self.sale_team_id.id if self.sale_team_id else False,
            },
        })
        return action

    def _fsm_create_sale_order(self):
        super(ProjectTask, self)._fsm_create_sale_order()
        if self.sale_order_id:
            self.sale_order_id.sudo().write({
                'from_maintenance': self.is_maintenance,
                'payment_term_id': self.env.ref('account.account_payment_term_immediate').id,
                'team_id': self.sale_team_id.id if self.sale_team_id else False,
            })

    def _fsm_create_sale_order_line(self):
        """ Generate sales order item based on the pricing_type on the project and the timesheets in the current task

            When the pricing_type = 'employee_rate', we need to search the employee mappings for the employee who timesheeted
            in the current task to retrieve the product in each mapping and generate an SOL for this product with the total
            hours of the related timesheet(s) as the ordered quantity. Some SOLs can be already generated if the user manually
            adds the SOL in the task or when he adds some materials in the tasks, a SO is generated.
            If the user manually adds in the SO some service products, we must check in these before generating new one.
            When no SOL is linked to the task before marking this task as done and no existing SOLs correspond to the default
            product in the project, we take the first SOL generated if no generated SOL contain the default product of the project.
            Here are the steps realized for this case:
                1) Get all timesheets in the tasks
                2) Classify this timesheets by employee
                3) Search the employee mappings (project.sale.line.employee.map model or the sale_line_employee_ids field in the
                   project model) for the employee who timesheets to have the product linked to the employee.
                4) Use the dict created in the second step to classify the timesheets in another dict in which the key is the id
                   and the price_unit of the product and the id uom. This information is important for the generation of the SOL.
                5) if no SOL is linked in the task then we add the default service project defined in the project into the dict
                   created in the previous step and value is the remaining timesheets.
                   That is, the ones are no impacted in the employee mappings (sale_line_employee_ids field) defined in the project.
                6) Classify the existing SOLs of the SO linked to the task, because the SO can be generated before the user clicks
                   on 'mark as done' button, for instance, when the user adds materials for this task. A dict is created containing
                   the id and price_unit of the product as key and the SOL(s) containing this product.
                    6.1) If no SOL is linked, then we check in the existing SOLs if there is a SOL with the default product defined
                        in the product, if it is the case then the SOL will be linked to the task.
                        This step can be useless if the user doesn't manually add a service product in the SO. In fact, this step
                        searchs in the SOLs of the SO, if there is an SOL with the default service product defined in the project.
                        If it is the case then the SOL will be linked to the task.
                7) foreach in the dict created in the step 4, in this loop, first of all, we search in the dict containing the
                   existing SOLs if the id of the product is containing in an existing SOL. If yes then, we don't generate an SOL
                   and link it to the timesheets linked to this product. Otherwise, we generate the SOL with the information containing
                   in the key and the timesheets containing in the value of the dict for this key.

            When the pricing_type = 'task_rate', we generate a sales order item with product_uom_qty is equal to the total hours of timesheets in the task.
            Once the SOL is generated we link this one to the task and its timesheets.
        """
        self.ensure_one()
        # Get all timesheets in the current task (step 1)
        not_billed_timesheets = self.env['account.analytic.line'].sudo().search([('task_id', '=', self.id), ('project_id', '!=', False), ('is_so_line_edited', '=', False)]).filtered(lambda t: t._is_not_billed())
        if self.pricing_type == 'employee_rate':
            # classify these timesheets by employee (step 2)
            timesheets_by_employee_dict = defaultdict(lambda: self.env['account.analytic.line'])  # key: employee_id, value: timesheets
            for timesheet in not_billed_timesheets:
                timesheets_by_employee_dict[timesheet.employee_id.id] |= timesheet

            # Search the employee mappings for the employees whose timesheets in the task (step 3)
            employee_mappings = self.env['project.sale.line.employee.map'].search([
                ('employee_id', 'in', list(timesheets_by_employee_dict.keys())),
                ('timesheet_product_id', '!=', False),
                ('project_id', '=', self.project_id.id)])

            # Classify the timesheets by product (step 4)
            product_timesheets_dict = defaultdict(lambda: self.env['account.analytic.line'])  # key: (timesheet_product_id.id, price_unit, uom_id.id), value: list of timesheets
            for mapping in employee_mappings:
                employee_timesheets = timesheets_by_employee_dict[mapping.employee_id.id]
                product_timesheets_dict[mapping.timesheet_product_id.id, mapping.price_unit, mapping.timesheet_product_id.uom_id.id] |= employee_timesheets
                not_billed_timesheets -= employee_timesheets  # we remove the timesheets because are linked to the mapping

            product = self.env['product.product']
            sol_in_task = bool(self.sale_line_id)
            if not sol_in_task:  # Then, add the default product of the project and remaining timesheets in the dict (step 5)
                default_product = self.project_id.timesheet_product_id
                if not_billed_timesheets:
                    # The remaining timesheets must be added in the sol with the default product defined in the fsm project
                    # if there is not SOL in the task
                    product = default_product
                    product_timesheets_dict[product.id, product.lst_price, product.uom_id.id] |= not_billed_timesheets
                elif (default_product.id, default_product.lst_price, default_product.uom_id.id) in product_timesheets_dict:
                    product = default_product

            # Get all existing service sales order items in the sales order (step 6)
            existing_service_sols = self.sudo().sale_order_id.order_line.filtered('is_service')
            sols_by_product_and_price_dict = defaultdict(lambda: self.env['sale.order.line'])  # key: (product_id, price_unit), value: sales order items
            for sol in existing_service_sols:  # classify the SOLs to easily find the ones that we want.
                sols_by_product_and_price_dict[sol.product_id.id, sol.price_unit] |= sol

            task_values = defaultdict()  # values to update the current task
            update_timesheet_commands = []  # used to update the so_line field of each timesheet in the current task.

            if not sol_in_task and sols_by_product_and_price_dict:  # Then check in the existing sol if a SOL has the default product defined in the project to set the SOL of the task (step 6.1)
                sol = sols_by_product_and_price_dict.get((self.project_id.timesheet_product_id.id, self.project_id.timesheet_product_id.lst_price))
                if sol:
                    task_values['sale_line_id'] = sol.id
                    sol_in_task = True

            for (timesheet_product_id, price_unit, uom_id), timesheets in product_timesheets_dict.items():
                sol = sols_by_product_and_price_dict.get((timesheet_product_id, price_unit))  # get the existing SOL with the product and the correct price unit
                if not sol:  # Then we create it
                    sol = self.env['sale.order.line'].sudo().create({
                        'order_id': self.sale_order_id.id,
                        'product_id': timesheet_product_id,
                        'price_unit': price_unit,
                        # The project and the task are given to prevent the SOL to create a new project or task based on the config of the product.
                        'project_id': self.project_id.id,
                        'task_id': self.id,
                        'product_uom_qty': sum(timesheets.mapped('unit_amount')),
                        'product_uom': uom_id,
                    })
                    # calling the onchange to handle discounts due to customer pricelists
                    sol._onchange_discount()

                # Link the SOL to the timesheets
                update_timesheet_commands.extend([fields.Command.update(timesheet.id, {'so_line': sol.id}) for timesheet in timesheets if not timesheet.is_so_line_edited])
                if not sol_in_task and (not product or (product.id == timesheet_product_id and product.lst_price == price_unit)):
                    # If there is no sol in task and the product variable is empty then we give the first sol in this loop to the task
                    # However, if the product is not empty then we search the sol with the same product and unit price to give to the current task
                    task_values['sale_line_id'] = sol.id
                    sol_in_task = True

            if update_timesheet_commands:
                task_values['timesheet_ids'] = update_timesheet_commands

            self.sudo().write(task_values)
        elif not self.sale_line_id:
            # Check if there is a SOL containing the default product of the project before to create a new one.
            sale_order_line = self.sale_order_id and self.sudo().sale_order_id.order_line.filtered(lambda sol: sol.product_id == self.project_id.timesheet_product_id)[:1]
            if not sale_order_line:
                sale_order_line = self.env['sale.order.line'].sudo().create({
                    'order_id': self.sale_order_id.id,
                    'product_id': self.timesheet_product_id.id,
                    'price_unit': self._cost_by_hour(not_billed_timesheets),#Custom by ALIADAS
                    # The project and the task are given to prevent the SOL to create a new project or task based on the config of the product.
                    'project_id': self.project_id.id,
                    'task_id': self.id,
                    'product_uom_qty': sum(timesheet_id.unit_amount for timesheet_id in not_billed_timesheets),
                })
                # calling the onchange to handle discounts due to customer pricelists
                sale_order_line._onchange_discount()
            self.sudo().write({  # We need to sudo in case the user cannot see all timesheets in the current task.
                'sale_line_id': sale_order_line.id,
                # assign SOL to timesheets
                'timesheet_ids': [fields.Command.update(timesheet.id, {'so_line': sale_order_line.id}) for timesheet in not_billed_timesheets if not timesheet.is_so_line_edited]
            })

    def _cost_by_hour(self,not_billed_timesheets):
        amount_by_hour = 1
        if not not_billed_timesheets:
            return amount_by_hour
        employee_id = not_billed_timesheets.employee_id
        if not employee_id:
            return amount_by_hour

        contract_id = self.env['hr.contract'].sudo().search([('employee_id','=',employee_id.id), ('company_id','=',self.company_id.id),('state','=','open')], limit=1)
        if not contract_id:
            return amount_by_hour
        resource_calendar_id = contract_id.resource_calendar_id
        if not resource_calendar_id:
            return amount_by_hour
        hours_per_week = resource_calendar_id.hours_per_week #horas por semana
        wage = contract_id.wage #Monto por contrato
        #aprox
        if wage > 0 and hours_per_week > 0:
            amount_by_hour = wage/hours_per_week
        else:
            return amount_by_hour
        return amount_by_hour