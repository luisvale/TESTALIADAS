from datetime import date, datetime, timedelta
from collections import defaultdict
import logging
_logger = logging.getLogger(__name__)

def eval_periodic_child(master):
    periodicity_line_ids = master.periodicity_line_ids
    now_date = date.today()
    #now_date = date(2023,6,30)
    #START : master update intervals
    maxim = len(periodicity_line_ids.ids)
    pos = 1
    x_pos = 0
    _logger.info("Iniciando actualización de intervalos")
    for z in periodicity_line_ids:
        if pos >= 1 and pos == maxim:
            z.sudo().write({'interval': periodicity_line_ids[0].days - 1})
            #Se resta -1 para que sea un día antes al de la sgte fecha : Tarea 1-12-2022
            #Ejm: t1 - 10 días , t2 - 20 días . T1 inicia 11-12-2022, termina 9 días despuesta(intervalo 10 días - 1)
        else:
            z.sudo().write({'interval': periodicity_line_ids[pos].days - z.days - 1})

        if x_pos == 0:
            z.sudo().write({'interval_start': z.days})
        else:
            z.sudo().write({'interval_start': z.days - periodicity_line_ids[x_pos-1].days})

        pos += 1
        x_pos += 1
    #Fin de actualización de intervalos

    level_to_assign = []

    # ÚLTIMO GENERADO
    child = master.env['maintenance.periodic'].sudo().search([('state', 'not in', ['cancel']), ('parent_id', '=', master.id)],
                                                             order="date_start DESC", limit=1)

    if not child or child and not child.analytic_line_ids:
        _logger.info("Sin hijos. Se contemplarán todos los niveles hasta la fecha.")
        days_past = (now_date - master.date_start).days
        periodicity_days = periodicity_line_ids.filtered(lambda l: l.days <= days_past)

        for periodic_line in periodicity_days:
            if periodic_line.level_id.id in master.analytic_line_ids.mapped('level_id').ids:
                new_date_start = master.date_start + timedelta(days=periodic_line.days)
                new_date_end = new_date_start + timedelta(days=periodic_line.interval)
                level_to_assign.append({
                    'start': new_date_start,
                    'end': new_date_end,
                    'lines': periodic_line
                })

    else:
        level_ids = child.analytic_line_ids.mapped('level_id') #Últimos niveles generados
        levels_analytic = master.analytic_line_ids.mapped('level_id')
        level_top = False
        for p in periodicity_line_ids:
            if p.level_id.id in levels_analytic.ids:
                level_top = p

        refresh = False
        if level_ids[0] == level_top:
            refresh = True

        _logger.info("Refresh %s " % refresh)

        if not refresh:
            level_pending_ids = periodicity_line_ids.mapped('level_id') - level_ids
        else:
            level_pending_ids = periodicity_line_ids.mapped('level_id')
        periodicity_days_to_do = periodicity_line_ids.filtered(lambda l: l.level_id.id in level_pending_ids.ids) #Periodicidad pendiente
        periodicity_done = periodicity_line_ids.filtered(lambda l: l.level_id.id in level_ids.ids) #Periodicidad realizada

        date_return = False
        for periodic_line in periodicity_days_to_do:
            if periodic_line.level_id.id in master.analytic_line_ids.mapped('level_id').ids:
                if not date_return:
                    date_return = child.date_end
                new_date_start = date_return + timedelta(days=1)
                if new_date_start <= now_date:
                    new_date_end = new_date_start + timedelta(days=periodic_line.interval)

                    date_return = new_date_end
                    #new_date_start = master.date_start + timedelta(days=periodic_line.days)
                    #new_date_end = new_date_start + timedelta(days=periodicity_days_to_do.interval)
                    level_to_assign.append({
                        'start': new_date_start,
                        'end': new_date_end,
                        'lines': periodic_line
                    })

    a=1
    return _create_maintenance_periodicity(master,level_to_assign)


def _create_maintenance_periodicity(master, level_to_assign):
    periodicity_line_ids = master.periodicity_line_ids
    data_to_create = []
    for line in level_to_assign:
        level_ids = line['lines'].mapped('level_id')
        #interval = periodicity_line_ids.filtered(lambda l: l.days == max_days).interval

        data_to_create.append({
            'parent_id': master.id,
            'date_start': line['start'],
            'date_end': line['end'],
            'level_ids': level_ids.ids
        })

    if data_to_create:
        _logger.info("MANTENIMIENTO ALIADAS: Procesando creación de mantenimientos ...")
        for data_list in data_to_create:
            try:
                child = master.sudo().copy(default={
                    'is_master': False,
                    'parent_id': data_list['parent_id'],
                    'date_start': data_list['date_start'],
                    'date_end': data_list['date_end']
                })
                if child:
                    _logger.info("MANTENIMIENTO ALIADAS: Mant.Periódico creado con ID %s" % child.id)
                    lines = master.analytic_line_ids.filtered(lambda a: a.level_id.id in data_list['level_ids'])
                    for line_to_copy in lines:
                        new_line = line_to_copy.sudo().copy(default={
                            'maintenance_id': child.id
                        })
                        if new_line:
                            _logger.info("Líneas creadas correctamente :)")
                        else:
                            _logger.info("Líneas no creada correctamente :(")
                else:
                    _logger.info("MANTENIMIENTO ALIADAS: Mant.Periódico NO creado")

            except Exception as e:
                _logger.warning("ALIADAS : Error de creación %s " % e)

        return "Proceso de creación de mantenimientos periódicos"
    else:
        return "Lamentablemente no hubo lista de datos para crear mant.periódicos"
