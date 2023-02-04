from . import controllers
from . import models
from . import wizard


from odoo.api import Environment, SUPERUSER_ID
import odoo
from odoo import http
import re
import os
from datetime import datetime
from odoo.http import request
import json
import requests
from user_agents import parse

def getting_ip(row):
    """This function calls the api and return the response"""
    url = f"https://freegeoip.app/json/{row}"       # getting records from getting ip address
    headers = {
        'accept': "application/json",
        'content-type': "application/json"
        }
    response = requests.request("GET", url, headers=headers)
    respond = json.loads(response.text)
    return respond

def post_init_hook(cr, registry):
    env = Environment(cr, SUPERUSER_ID, {})
    user_ids = []
    for user in env['res.users'].search([]):
        if user.has_group('base.group_user'):
            user_ids.append(user.id)
    env.ref('advanced_session_management.group_login_log_user_ah').users = [(6,0,user_ids)]
    for fname in os.listdir(odoo.tools.config.session_dir):
        path = os.path.join(odoo.tools.config.session_dir, fname)
        name = re.split('_|\\.', fname)
        session_store = http.root.session_store
        get_session = session_store.get(name[1])
        if get_session.db:
            if get_session.uid:
                os.unlink(path)
                get_session.logout(keep_db=True)
                # try:
                #     ip = ''
                #     if 'HTTP_X_REAL_IP' in request.httprequest.environ.keys():
                #         ip = request.httprequest.environ['HTTP_X_REAL_IP']
                #     # loc_res = DbIpCity.get(ip, api_key='free')
                #     # loc_res = requests.get('http://ipinfo.io/json')
                #     # value = json.loads(loc_res.text)
                #     value = getting_ip(ip)
                #     country = value['country_name'] or ''
                #     city = value['city'] or ''
                #     state = value['region_name'] or ''
                # except:
                #     country = ''
                #     state = ''
                #     city = ''
                # user_agent = parse(request.httprequest.environ.get('HTTP_USER_AGENT', ''))
                # device = user_agent.device.family
                # if user_agent.device.family == 'Other':
                #     if user_agent.is_pc:
                #         device = 'PC'
                #     elif user_agent.is_mobile:
                #         device = 'Mobile'
                #     elif user_agent.is_tablet:
                #         device = 'Tablet'    
                # env['login.log'].sudo().create({
                #     'user_id':get_session.uid,
                #     'user_agent':user_agent,
                #     'browser':user_agent.browser.family,
                #     'device':device,
                #     'os':user_agent.os.family,
                #     # 'ip':ip,
                #     'login_date':datetime.now(),
                #     'session_id':get_session.sid,
                #     'state':'active',
                #     # 'country':country,
                #     # 'loc_state':state,
                #     # 'city':city
                # })
            # else:
                # os.unlink(path)
                # get_session.logout(keep_db=True)

def uninstall_hook(cr, registry):
    env = Environment(cr, SUPERUSER_ID, {})
    env['ir.config_parameter'].search([('key','=','advanced_session_management.send_mail')]).unlink()
