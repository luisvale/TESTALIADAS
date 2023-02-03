# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date
import logging

_logger = logging.getLogger(__name__)
from datetime import date, datetime
import json


class ProjectTaskTimeWizard(models.TransientModel):
    _name = 'project.time.task.wizard'
    _description = 'Tareas: Manejo de tiempo mediante wizard'

    task_id = fields.Many2one('project.task', string='Tarea')
    display_timer_start_primary = fields.Boolean(compute='_compute_display_timer_buttons')
    display_timer_start_secondary = fields.Boolean(compute='_compute_display_timer_buttons')
    encode_uom_in_days = fields.Boolean(compute='_compute_display_timer_buttons')
    display_timer_stop = fields.Boolean(compute='_compute_display_timer_buttons')
    display_timer_pause = fields.Boolean(compute='_compute_display_timer_buttons')
    display_timer_resume = fields.Boolean(compute='_compute_display_timer_buttons')
    timer_start = fields.Datetime(compute='_compute_display_timer_buttons')
    timer_pause = fields.Datetime(compute='_compute_display_timer_buttons')
    # display_timer_start_primary = fields.Boolean(related='task_id.display_timer_start_primary')
    # display_timer_start_secondary = fields.Boolean(related='task_id.display_timer_start_secondary')
    # encode_uom_in_days = fields.Boolean(related='task_id.encode_uom_in_days')
    # display_timer_stop = fields.Boolean(related='task_id.display_timer_stop')
    # display_timer_pause = fields.Boolean(related='task_id.display_timer_pause')
    # display_timer_resume = fields.Boolean(related='task_id.display_timer_resume')
    # timer_start = fields.Boolean(related='task_id.timer_start')

    @api.depends('task_id.display_timer_start_primary', 'task_id.display_timer_start_secondary',
                 'task_id.encode_uom_in_days',
                 'task_id.display_timer_stop',
                 'task_id.display_timer_pause',
                 'task_id.display_timer_resume',
                 'task_id.timer_start',
                 )
    def _compute_display_timer_buttons(self):
        for record in self:
            if record.task_id.child_ids:
                raise ValidationError(_("Solo puede tomar el tiempo de Sub Tareas."))

            display_timer_start_primary = record.task_id.display_timer_start_primary
            display_timer_start_secondary = record.task_id.display_timer_start_secondary
            encode_uom_in_days = record.task_id.encode_uom_in_days
            display_timer_stop = record.task_id.display_timer_stop
            display_timer_pause = record.task_id.display_timer_pause
            display_timer_resume = record.task_id.display_timer_resume
            timer_start = record.task_id.timer_start
            timer_pause = record.task_id.timer_pause

            record.update({
                'display_timer_start_primary': display_timer_start_primary,
                'display_timer_start_secondary': display_timer_start_secondary,
                'encode_uom_in_days': encode_uom_in_days,
                'display_timer_stop': display_timer_stop,
                'display_timer_pause': display_timer_pause,
                'display_timer_resume': display_timer_resume,
                'timer_start': timer_start,
                'timer_pause': timer_pause,
            })

            a=1


    def action_timer_start(self):
        if self.task_id:
            return self.task_id.action_timer_start()


    def action_timer_stop(self):
        if self.task_id:
            return self.task_id.action_timer_stop()


    def action_timer_pause(self):
        if self.task_id:
            return self.task_id.action_timer_pause()


    def action_timer_resume(self):
        if self.task_id:
            return self.task_id.action_timer_resume()
