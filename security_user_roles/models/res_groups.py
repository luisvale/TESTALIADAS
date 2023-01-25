# -*- coding: utf-8 -*-

from lxml import etree
from lxml.builder import E

from odoo import _, api, fields, models

from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
from odoo.addons.base.models.res_users import name_boolean_group, name_selection_groups


class res_groups(models.Model):
    """
    Re write to update xml view of security roles
    """
    _inherit = "res.groups"

    @api.model
    def _update_user_groups_view(self):
        """
        Re-write to update view of security role
        """
        super(res_groups, self)._update_user_groups_view()
        self._update_security_role_view()

    @api.model
    def _update_security_role_view(self):
        """
        The method to prepare the view of rights the same as a user form view (mostly copied as for users view in base)
        """
        self = self.with_context(lang=None)
        view = self.sudo().env.ref("security_user_roles.security_groups_view", raise_if_not_found=False)
        if not (view and view.exists() and view._name == 'ir.ui.view'):
            return

        if self._context.get("install_filename") or self._context.get(MODULE_UNINSTALL_FLAG):
            xml = E.field(name="group_ids", position="after")
        else:
            group_no_one = view.env.ref("base.group_no_one")
            group_employee = view.env.ref("base.group_user")
            xml1, xml2, xml3 = [], [], []
            xml_by_category = {}
            xml1.append(E.separator(string="User Type", colspan="2", groups="base.group_no_one"))
            user_type_field_name = ""
            user_type_readonly = str({})
            sorted_tuples = sorted(self.get_groups_by_application(),
                                   key=lambda t: t[0].xml_id != "base.module_category_user_type")


            for app, kind, gs, category_name in sorted_tuples: 
                attrs = {}
                if app.xml_id in self._get_hidden_extra_categories():
                    attrs["groups"] = "base.group_no_one"
                if app.xml_id == "base.module_category_user_type":
                    field_name = name_selection_groups(gs.ids)
                    user_type_field_name = field_name
                    user_type_readonly = str({"readonly": [(user_type_field_name, "!=", group_employee.id)]})
                    attrs["widget"] = "radio"
                    attrs["groups"] = "base.group_no_one"
                    xml1.append(E.field(name=field_name, **attrs))
                    xml1.append(E.newline())
                elif kind == "selection":
                    field_name = name_selection_groups(gs.ids)
                    attrs["attrs"] = user_type_readonly
                    if category_name not in xml_by_category:
                        xml_by_category[category_name] = []
                        xml_by_category[category_name].append(E.newline())
                    xml_by_category[category_name].append(E.field(name=field_name, **attrs))
                    xml_by_category[category_name].append(E.newline())
                else:
                    app_name = app.name or "Other"
                    xml3.append(E.separator(string=app_name, colspan="4", **attrs))
                    attrs["attrs"] = user_type_readonly
                    for g in gs:
                        field_name = name_boolean_group(g.id)
                        if g == group_no_one:
                            xml3.append(E.field(name=field_name, invisible="1", **attrs))
                        else:
                            xml3.append(E.field(name=field_name, **attrs))

            xml3.append({"class": "o_label_nowrap"})
            if user_type_field_name:
                user_type_attrs = {"invisible": [(user_type_field_name, "!=", group_employee.id)]}
            else:
                user_type_attrs = {}

            for xml_cat in sorted(xml_by_category.keys(), key=lambda it: it[0]):
                xml_cat_name = xml_cat[1]
                master_category_name = (_(xml_cat_name))
                xml2.append(E.group(*(xml_by_category[xml_cat]), col="2", string=master_category_name))
            xml = E.field(
                E.group(*(xml1), col="2"),
                E.group(*(xml2), col="2", attrs=str(user_type_attrs)),
                E.group(*(xml3), col="4", attrs=str(user_type_attrs)), name="group_ids", position="replace")
            xml.addprevious(etree.Comment("GENERATED AUTOMATICALLY BY SECURITY USER ROLES"))
            
        xml_content = etree.tostring(xml, pretty_print=True, encoding="unicode")
        if xml_content != view.arch:
            new_context = dict(view._context)
            new_context.pop("install_filename", None)
            new_context["lang"] = None
            view.with_context(new_context).write({"arch": xml_content})
