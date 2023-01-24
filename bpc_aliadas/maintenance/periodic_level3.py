from datetime import date, datetime, timedelta
from collections import defaultdict
import logging
_logger = logging.getLogger(__name__)

def eval_periodic_child(master):
    periodicity_line_ids = master.periodicity_line_ids
    #now_date = date.today()
    now_date = date(2023,2,26)
    #START : master update intervals
    maxim = len(periodicity_line_ids.ids)
    pos = 1
    _logger.info("Iniciando actualización de intervalos")
    for z in periodicity_line_ids:
        if pos >= 1 and pos == maxim:
            z.sudo().write({'interval': periodicity_line_ids[0].days - 1})
            #Se resta -1 para que sea un día antes al de la sgte fecha : Tarea 1-12-2022
            #Ejm: t1 - 10 días , t2 - 20 días . T1 inicia 11-12-2022, termina 9 días despuesta(intervalo 10 días - 1)
        else:
            z.sudo().write({'interval': periodicity_line_ids[pos].days - z.days - 1})

        pos += 1
    #Fin de actualización de intervalos

    #Agrupación
    group_factory = []
    q = 1
    _logger.info("Agrupando niveles")
    for level in periodicity_line_ids:
        y = master.env['maintenance.periodicity.line'].sudo()
        for i in range(0, q):
            y += periodicity_line_ids[i]
            # y.append(periodicity_line_ids[i])
        group_factory.append(y)
        q += 1

    if group_factory:
        level_to_assign = defaultdict(list)

        #LLegó al nivel máximo
        upper_level = False

        #ÚLTIMO GENERADO
        child = master.env['maintenance.periodic'].sudo().search([('state', 'not in', ['cancel']), ('parent_id', '=', master.id)],
                                                                 order="date_start DESC", limit=1)
        if not child:
            _logger.info("Sin hijos. Se contemplarán todos los niveles hasta la fecha.")
            days_past = (now_date - master.date_start).days
            for x in group_factory:
                max_days = max(x.mapped('days'))
                if days_past >= max_days:
                    new_date_start = master.date_start + timedelta(days=max_days)
                    level_to_assign[new_date_start].append(x)
                    #level_to_assign.append(x)
            #level_to_assign = group_factory
        else:
            last_line_level = periodicity_line_ids[len(periodicity_line_ids.ids)-1] #última línea de nivel de mi tarea master
            level_last = last_line_level.level_id #último nivel de mi tarea master
            leve_ids = child.analytic_line_ids.mapped('level_id').ids #ids de niveles de mi tareas hijas
            if level_last.id in leve_ids:
                _logger.info("Llegó al nivel TOP. Se tomará en cuenta reinicio de proceso de generación de mantenimientos periódicos.")
                upper_level = True #Reiniciar el proceso de generación de mant.periódicos
            else:
                _logger.info("Aún no llega al nivel TOP, se tomarán los niveles faltantes")
                upper_level = False #Continuar con los niveles faltantes

            if not upper_level:
                parent_periodicity_level_ids = master.periodicity_line_ids.mapped('level_id') #todos los niveles del padre
                child_analytic_line_ids = child.analytic_line_ids
                all_level_ids = child_analytic_line_ids.mapped('level_id')  # todos los niveles de mi mant. periódico hasta el momento
                lack_levels = parent_periodicity_level_ids - all_level_ids # niveles faltante
                sum_intervals = 0
                for level_id in lack_levels:
                    for g in group_factory:
                        leve_ids = g.mapped('level_id')
                        if level_id.id not in leve_ids.ids:
                            pass
                        else:
                            #¿A pesar que no está, debería agregarlo?
                            #Revisar el intervalo del nivel y si sumado a la fecha final es menor a hoy
                            line_periodicity = master.periodicity_line_ids.filtered(lambda l:l.level_id.id == level_id.id)
                            interval = line_periodicity.interval + 1
                            #days = line_periodicity.days  # INTERVAL + 1
                            nex_date_start = child.date_start + timedelta(days=interval + sum_intervals)
                            if nex_date_start <= now_date: #evaluo si la próxima fecha de inicio de una hipotética tarea periódica es menor a la fecha de hoy
                                level_to_assign[nex_date_start].append(g)
                                sum_intervals += interval
                                #level_to_assign.append(g)
                                break
            else:
                parent_periodicity_level_ids = master.periodicity_line_ids.mapped('level_id')  # todos los niveles del padre
                sum_intervals = 0
                for level_id in parent_periodicity_level_ids:
                    for g in group_factory:
                        leve_ids = g.mapped('level_id')
                        if level_id.id not in leve_ids.ids:
                            pass
                        else:
                            # ¿A pesar que no está, debería agregarlo?
                            # Revisar el intervalo del nivel y si sumado a la fecha final es menor a hoy
                            line_periodicity = master.periodicity_line_ids.filtered(lambda l: l.level_id.id == level_id.id)
                            interval = line_periodicity.interval + 1
                            days = line_periodicity.days #INTERVAL + 1
                            nex_date_start = child.date_start + timedelta(days=days + sum_intervals)
                            if nex_date_start <= now_date:  # evaluo si la próxima fecha de inicio de una hipotética tarea periódica es menor a la fecha de hoy
                                level_to_assign[nex_date_start].append(g)
                                sum_intervals += days
                                # level_to_assign.append(g)
                                break

                #level_to_assign = group_factory

        return _create_maintenance_periodicity(master, child, upper_level, level_to_assign)

    else:
        return "No hay niveles a asignar. Lista vacía."


def _create_maintenance_periodicity(master, child, upper_level, level_to_assign):
    periodicity_line_ids = master.periodicity_line_ids
    data_to_create = []
    for date_start, level_list in level_to_assign.items():
        level_ids = level_list[0].mapped('level_id')
        max_days = max(level_list[0].mapped('days'))
        interval = periodicity_line_ids.filtered(lambda l: l.days == max_days).interval

        new_date_start = date_start
        new_date_end = date_start + timedelta(days=interval)

        data_to_create.append({
            'parent_id': master.id,
            'date_start': new_date_start,
            'date_end': new_date_end,
            'level_ids': level_ids.ids
        })

    if data_to_create:
        _logger.info("MANTENIMIENTO ALIADAS: Procesando creación de mantenimientos ...")
        for data_list in data_to_create:
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

        return "Proceso de creación de mantenimientos periódicos"
    else:
        return "Lamentablemente no hubo lista de datos para crear mant.periódicos"
