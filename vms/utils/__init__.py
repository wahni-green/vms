# Copyright (c) 2024, Wahni IT Solutions Pvt Ltd and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist()
def get_sales_orders(vehicle_allocation, route, territory):
    route = frappe.parse_json(route)
    territory = frappe.parse_json(territory)

    alloc_to_exclude = (
        frappe.db.get_all("Vehicle Allocation", filters={"docstatus": 0}, pluck="name")
        or []
    )
    alloc_to_exclude.append(vehicle_allocation)
    exclude = []
    if alloc_to_exclude:
        exclude = frappe.db.get_all(
            "Lot Allocation Order",
            filters={"parent": ["in", alloc_to_exclude]},
            pluck="sales_order_row",
        )

    so = frappe.qb.DocType("Sales Order")
    soi = frappe.qb.DocType("Sales Order Item")

    DateFormat = CustomFunction("DATE_FORMAT", ["date", "format"])
    orders = []
    company_list = frappe.db.get_all("Company", pluck="name", order_by="name desc")
    for company in company_list:
        result = (
            frappe.qb.from_(so)
            .inner_join(soi)
            .on(soi.parent == so.name)
            .select(
                so.name.as_("sales_order"),
                so.customer,
                DateFormat(so.transaction_date, "%d-%m-%Y").as_("date"),
                so.company,
                so.transaction_date,
                so.route,
                soi.name.as_("sales_order_detail"),
                soi.item_code.as_("item"),
                (soi.qty - soi.allocated_qty).as_("qty"),
                soi.rate,
                soi.uom,
                soi.stock_qty,
                (
                    soi.weight_per_unit
                    * (soi.qty - soi.allocated_qty)
                ).as_("total_weight"),
            )
            .where(so.docstatus == 1)
            .where(so.company == company)
            .where(so.status != "Closed")
            .where(soi.allocated_qty < soi.qty)
            .orderby(so.transaction_date)
        )
        if exclude:
            result = result.where(soi.name.notin(exclude))
        if territory:
            result = result.where(so.territory.isin(territory))
        if route:
            result = result.where(so.route.isin(route))

        orders += result.run(as_dict=True) or []

    return orders