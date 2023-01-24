from datetime import date, datetime, timedelta
import logging
_logger = logging.getLogger(__name__)

def eval_periodic_child(master):
    date_start = master.date_start
    periodicity_line_ids = master.periodicity_line_ids
    now = date.today()

    days = (now - date_start).days

    #START : master update intervals
    maxim = len(periodicity_line_ids.ids)
    pos = 1
    for z in periodicity_line_ids:
        if pos >= 1 and pos == maxim:
            z.sudo().write({'interval': periodicity_line_ids[0].days})
        else:
            z.sudo().write({'interval': periodicity_line_ids[pos].days - z.days})
    #Fin de actualización de intervalos

    group_factory = []
    q = 1
    for level in periodicity_line_ids:
        if days >= level.days:
            y = master.env['maintenance.periodicity.line'].sudo()
            for i in range(0, q):
                y += periodicity_line_ids[i]
                #y.append(periodicity_line_ids[i])
            group_factory.append(y)
            q += 1

    if group_factory:
        level_to_assign = []
        childs = master.env['maintenance.periodic'].sudo().search([('state','not in', ['cancel']), ('parent_id','=',master.id)])
        if childs:
            for lev in group_factory:
                ids = lev.mapped('level_id').ids
                count = 0
                for i in ids:
                    for x in childs.analytic_line_ids:
                        if x.level_id.id == i:
                            count += 1
                            break

                if count == len(ids):
                    pass
                else:
                    level_to_assign.append(lev)

                # child = childs.analytic_line_ids.filtered(lambda a:a.level_id.id in ids)
                # if not child:
                #     level_to_assign.append(lev)

        else:
            level_to_assign = group_factory

        if level_to_assign:
            for level_list in level_to_assign:
                level_ids = level_list.mapped('level_id')
                max_days = max(level_list.mapped('days'))
                new_date_start = master.date_start + timedelta(days=max_days)
                new_date_end = False
                periodicity_days = periodicity_line_ids.filtered(lambda l:l.days > max_days)
                if periodicity_days:
                    days_min = min(periodicity_days.mapped('days'))
                    new_date_end = master.date_start + timedelta(days=days_min)
                else:
                    if len(periodicity_line_ids.ids) > 1:
                        line_last_ant = periodicity_line_ids[len(periodicity_line_ids.ids)-2]
                        line_last_ant_day = line_last_ant.days
                        nex_day = max_days - line_last_ant_day
                        new_date_end = new_date_start + timedelta(days=nex_day)
                    else:
                        new_date_end = new_date_start + timedelta(days=max_days)

                _logger.info("ALIADAS: Niveles a crear %s de master name %s " % (level_ids.ids, master.name))

                child = master.sudo().copy(default={
                    'is_master': False,
                    'parent_id': master.id,
                    'date_start': new_date_start,
                    'date_end': new_date_end,
                })
                lines = master.analytic_line_ids.filtered(lambda a: a.level_id.id in level_ids.ids)
                for line_to_copy in lines:
                    new_line = line_to_copy.sudo().copy(default={
                        'maintenance_id': child.id
                    })
                    if new_line:
                        _logger.info("Líneas creadas correctamente :)")
                    else:
                        _logger.info("Líneas no creada correctamente :(")
            return True
        else:
            #CASO EN LA CUAL YA HAY MANT.PERIÓDICOS CON TODOS LOS NIVELES .
            _logger.info("ALIADAS: No hubo niveles para asignar")
            return False
    else:
        return False



def _find_last_level(master):
    childs = master.env['maintenance.periodic'].sudo().search([('state', 'not in', ['cancel']), ('parent_id', '=', master.id)])