// Copyright(c) 2024, Wahni IT Solutions Pvt.Ltd.and contributors
// For license information, please see license.txt

frappe.provide("vms");

const isObjectEmpty = (objectName) => {
	return objectName && Object.keys(objectName).length === 0 && objectName.constructor === Object;
};

// eslint-disable-next-line
vms.isObjectEmpty = isObjectEmpty;

// eslint-disable-next-line
vms.OrderSelector = class OrderSelector {
	constructor(frm) {
		this.dialog = new frappe.ui.Dialog({
			title: __("Get Order Items"),
			size: "extra-large",
			fields: [
				{ fieldtype: "Section Break" },
				{ fieldtype: "HTML", fieldname: "results_area" },
			],
		});
		this.frm = frm;
	}

	init() {
		if (this.frm.is_dirty()) {
			frappe.msgprint(__("Please save the document before adding items."));
			return;
		}
		if (this.frm.doc.docstatus != 0) {
			frappe.msgprint(__("Cannot add items to submitted/cancelled document."));
			return;
		}

		this.allocated_order_items = {};
		frappe.run_serially([() => this.setup_wrapper(), () => this.get_data()]);
	}

	setup_wrapper() {
		this.dialog.fields_dict.results_area.$wrapper.empty();
		this.wrapper = this.dialog.fields_dict.results_area.$wrapper.append(`
			<div class="calculation" style="border: 1px; border-radius: 3px; height: 170px; margin-bottom: 10px; margin-top: -40px;"></div>
			<div class="orders" style="display:inline-block; border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto; width: 63%;"></div>
			<div class="results" style="display:inline-block; border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto; width: 36%;"></div>
		`);

		this.orders = this.wrapper.find(".orders");
		this.results = this.wrapper.find(".results");
		this.placeholder = $(`
			<div class="multiselect-empty-state">
				<span class="text-center" style="margin-top: -40px;">
					<i class="fa fa-2x text-extra-muted"></i>
					<p class="text-extra-muted">No orders found</p>
				</span>
			</div>
		`);

		this.calculation = this.wrapper.find(".calculation");
		this.calculation_placeholder = $(`
			<table class="table">
				<thead>
					<tr>
						<th class="text-center"></th>
						<th class="text-center">Qty</th>
						<th class="text-center">Kg</th>
					</tr>
				</thead>
				<tbody>
					<tr>
						<td class="text-center">Capacity</td>
						<td class="text-center">${flt(this.frm.doc.qty_capacity, 2)}</td>
						<td class="text-center">${flt(this.frm.doc.weight_capacity, 2)}</td>
					</tr>
					<tr>
						<td class="text-center">Allocated</td>
						<td class="pop_allotted_qty text-center">${flt(this.frm.doc.allocated_qty, 2)}</td>
						<td class="pop_allotted_wt text-center">${flt(this.frm.doc.allocated_weight, 2)}</td>
					</tr>
					<tr>
						<td class="text-center">Remaining</td>
						<td class="pop_rem_qty text-center">${flt(
							this.frm.doc.qty_capacity - this.frm.doc.allocated_qty,
							2
						)}</td>
						<td class="pop_rem_wt text-center">${flt(
							this.frm.doc.weight_capacity - this.frm.doc.allocated_weight,
							2
						)}</td>
					</tr>
				</tbody>
			</table>
		`);

		this.calculation.empty();
		this.calculation.append(this.calculation_placeholder);

		this.results.on("click", ".list-item--head :checkbox", (e) => {
			this.results
				.find(".list-item-container .list-row-check")
				.prop("checked", $(e.target).is(":checked"));
			if ($(e.target).is(":checked")) {
				let checked_items = this.get_checked_values(this.results);
				checked_items.forEach((item) => {
					if (!this.allocated_order_items[item.sales_order]) {
						this.allocated_order_items[item.sales_order] = {};
					}
					this.allocated_order_items[item.sales_order][item.sales_order_detail] = item;
					this.set_selected_order_bg(item.sales_order, "lightblue");
				});
			} else {
				let unchecked_items = this.get_unchecked_values(this.results);
				unchecked_items.forEach((item) => {
					if (this.allocated_order_items[item.sales_order]?.[item.sales_order_detail]) {
						delete this.allocated_order_items[item.sales_order][
							item.sales_order_detail
						];
					}
					// eslint-disable-next-line
					if (vms.isObjectEmpty(this.allocated_order_items[item.sales_order])) {
						this.set_selected_order_bg(item.sales_order, "transparent");
						delete this.allocated_order_items[item.sales_order];
					}
				});
			}
			this.refresh_capacity();
		});

		this.results.on("click", ".list-row-check", (e) => {
			let selected_so = $(e.target).closest(".list-item-container").attr("data-so");
			if (!selected_so) return;

			if (!this.allocated_order_items[selected_so]) {
				this.allocated_order_items[selected_so] = {};
			}

			let row = $(e.target).closest(".list-item-container");
			let so_detail = row.attr("data-so-detail");
			if (
				$(e.target).is(":checked") &&
				!this.allocated_order_items[selected_so][so_detail]
			) {
				this.allocated_order_items[selected_so][so_detail] = {
					qty: Number(row.attr("data-qty")),
					order_qty: Number(row.attr("data-order-qty")),
					weight: Number(row.attr("data-weight")),
					customer: row.attr("data-customer"),
					item: row.attr("data-item"),
					route: row.attr("data-route"),
					company: row.attr("data-company"),
					sales_order: row.attr("data-so"),
					sales_order_detail: row.attr("data-so-detail"),
				};
				this.set_selected_order_bg(selected_so, "lightblue");
			} else {
				if (this.allocated_order_items[selected_so][so_detail]) {
					delete this.allocated_order_items[selected_so][so_detail];
				}
				// eslint-disable-next-line
				if (vms.isObjectEmpty(this.allocated_order_items[selected_so])) {
					this.set_selected_order_bg(selected_so, "transparent");
					delete this.allocated_order_items[selected_so];
				}
			}
			this.refresh_capacity();
		});

		this.orders.on("click", ".list-item--head :checkbox", (e) => {
			this.results.empty();
			if ($(e.target).is(":checked")) {
				this.orders.find(".list-item-container .list-row-check").each((idx, el) => {
					let selected_so = $(el).attr("data-so");
					let items = this.data.message.items[selected_so];
					if (!items || !selected_so) return;
					if (!this.allocated_order_items[selected_so]) {
						this.allocated_order_items[selected_so] = {};
					}

					items.forEach((item) => {
						this.allocated_order_items[selected_so][item.sales_order_detail] = item;
					});
				});
				this.set_all_order_bg("lightblue");
			} else {
				this.allocated_order_items = {};
				this.set_all_order_bg("transparent");
			}
			this.refresh_capacity();
		});

		this.orders.on("click", ".list-row-check", (e) => {
			let selected_so = $(e.target).closest(".list-item-container").attr("data-so");
			if (!selected_so) return;
			if ($(e.target).is(":checked")) {
				this.orders
					.find(".list-item-container .list-row-check")
					.filter((i, el) => {
						return $(el).attr("data-so") != selected_so;
					})
					.prop("checked", 0);
			}
			this.results.empty();
			this.results.append(this.make_list_row(this.item_columns));
			let items = this.data.message.items[selected_so];
			if (!items) return;
			items.forEach((item) => {
				item.checked = this.allocated_order_items[selected_so]?.[item.sales_order_detail]
					? true
					: false;
				this.results.append(this.make_list_row(this.item_columns, item, true));
			});
			if (!this.allocated_order_items[selected_so]) {
				this.results.find(".list-item--head :checkbox").click();
			}
		});
	}

	set_selected_order_bg(order, colour) {
		this.orders
			.find(".list-item-container")
			.filter((i, el) => {
				return $(el).attr("data-so") == order;
			})
			.css("background-color", colour);
	}

	set_all_order_bg(colour) {
		this.orders.find(".list-item-container").css("background-color", colour);
	}

	refresh_capacity() {
		let allocated_qty = this.frm.doc.allocated_qty || 0;
		let allocated_wt = this.frm.doc.allocated_weight || 0;

		for (const order in this.allocated_order_items) {
			for (const item in this.allocated_order_items[order]) {
				allocated_qty += Number(this.allocated_order_items[order][item].qty);
				allocated_wt += Number(this.allocated_order_items[order][item].weight);
			}
		}

		if (this.frm.doc.qty_capacity > allocated_qty) {
			$(".pop_rem_qty").html(
				`<span style="color: green">${flt(
					this.frm.doc.qty_capacity - allocated_qty,
					2
				)}</span>`
			);
		} else {
			$(".pop_rem_qty").html(
				`<span style="color: red">${flt(
					this.frm.doc.qty_capacity - allocated_qty,
					2
				)}</span>`
			);
		}

		if (this.frm.doc.weight_capacity > allocated_wt) {
			$(".pop_rem_wt").html(
				`<span style="color: green">${flt(
					this.frm.doc.weight_capacity - allocated_wt,
					2
				)}</span>`
			);
		} else {
			$(".pop_rem_wt").html(
				`<span style="color: red">${flt(
					this.frm.doc.weight_capacity - allocated_wt,
					2
				)}</span>`
			);
		}

		$(".pop_allotted_qty").text(allocated_qty);
		$(".pop_allotted_wt").text(allocated_wt);
	}

	async get_data() {
		let me = this;
		me.item_columns = ["item", "qty", "weight"];
		me.order_columns = ["sales_order", "customer", "date", "company"];
		me.results.empty();

		me.data = await this.frm.call("get_order_items");
		let orders = me.data.message.orders;

		if (orders && orders.length > 0) {
			me.results.append(me.make_list_row(me.item_columns));
			me.orders.append(me.make_list_row(me.order_columns, {}, true));
			orders.forEach((order) => {
				me.orders.append(me.make_list_row(me.order_columns, order, true));
			});
		} else {
			me.results.append(me.placeholder);
			me.orders.append(me.placeholder);
		}

		this.set_primary_action(me.results);
		me.dialog.show();
	}

	set_primary_action($results) {
		let me = this;
		this.dialog.set_primary_action(__("Add"), function () {
			// eslint-disable-next-line
			if (!vms.isObjectEmpty(me.allocated_order_items)) {
				for (const order in me.allocated_order_items) {
					for (const item in me.allocated_order_items[order]) {
						let data = me.allocated_order_items[order][item];
						let row = me.frm.add_child("orders");
						row.sales_order = data.sales_order;
						row.sales_order_detail = data.sales_order_detail;
						row.customer = data.customer;
						row.company = data.company;
						row.item = data.item;
						row.order_qty = data.order_qty;
						row.allocated_qty = data.qty;
						row.pending_qty = data.qty;
						row.unit_weight = flt(data.weight / data.qty, 2);
						row.allocated_weight = data.weight;
						row.route = data.route || "";
					}
				}
				me.frm.refresh_fields();
				me.frm.trigger("set_allocated");
				me.dialog.hide();
				me.frm.save().then(() => {
					me.init();
				});
			} else {
				frappe.msgprint(__("Please select order items."));
			}
		});
	}

	make_list_row(columns, result = {}, is_order = false) {
		let contents = ``;
		// eslint-disable-next-line
		let head = vms.isObjectEmpty(result);
		let field_width_mapping = {
			sales_order: 190,
			customer: 170,
			date: 100,
			item: 200,
			qty: 40,
			weight: 50,
		};

		columns.forEach(function (column) {
			if (field_width_mapping[column]) {
				contents += `<div
                    class="list-item__content ellipsis"
                    style="flex: 0 0 ${field_width_mapping[column]}px;"
                >`;
			} else {
				contents += `<div class="list-item__content ellipsis">`;
			}

			if (head) {
				contents += `<span class="ellipsis">${__(frappe.model.unscrub(column))}</span>`;
			} else {
				if (column == "sales_order") {
					contents += `<a
                        class="list-id ellipsis"
                        href="/app/sales-order/${__(result[column])}"
                        target="_blank"
                    >${__(result[column])}</a>`;
				} else {
					contents += `<span class="ellipsis">${__(result[column])}</span>`;
				}
			}
			contents += `</div>`;
		});

		let $row = $(`
            <div class="list-item">
		        <div class="list-item__content" style="flex: 0 0 10px;">
			        <input
                        type="checkbox"
                        class="list-row-check"
                        ${result.sales_order ? `data-so="${result.sales_order}"` : ""}
                        ${
							result.sales_order_detail
								? `data-so-detail="${result.sales_order_detail}"`
								: ""
						}
                        ${result.checked ? "checked" : ""}
                    >
		        </div>
		        ${contents}
	        </div>
        `);

		$row = this.list_row_data_items(head, $row, result);
		return $row;
	}

	list_row_data_items(head, $row, result) {
		if (head) {
			$row.addClass("list-item--head");
		} else {
			$row = $(`
                <div class="list-item-container"
                    data-so = "${result.sales_order}"
                    data-so-detail = "${result.sales_order_detail}"
                    data-customer = "${result.customer}"
                    data-company = "${result.company}"
                    data-item = "${result.item}"
                    data-weight = "${result.weight}"
                    data-rate = "${result.rate}"
                    data-order-qty = "${result.order_qty}"
                    data-qty = "${result.qty}"
                    data-route = "${result.route}"
                    data-transaction-date = "${result.transaction_date}"
                >
                </div>
            `).append($row);
		}
		return $row;
	}

	get_checked_values($results) {
		return $results
			.find(".list-item-container")
			.map(function () {
				let checked_values = {};
				if ($(this).find(".list-row-check:checkbox:checked").length > 0) {
					checked_values["sales_order"] = $(this).attr("data-so");
					checked_values["sales_order_detail"] = $(this).attr("data-so-detail");
					checked_values["customer"] = $(this).attr("data-customer");
					checked_values["company"] = $(this).attr("data-company");
					checked_values["item"] = $(this).attr("data-item");
					checked_values["qty"] = Number($(this).attr("data-qty"));
					checked_values["order_qty"] = Number($(this).attr("data-order-qty"));
					checked_values["rate"] = Number($(this).attr("data-rate"));
					checked_values["weight"] = Number($(this).attr("data-weight"));
					checked_values["route"] = $(this).attr("data-route");
					checked_values["transaction_date"] = $(this).attr("data-transaction-date");

					return checked_values;
				}
			})
			.get();
	}

	get_unchecked_values($results) {
		return $results
			.find(".list-item-container")
			.map(function () {
				let checked_values = {};
				if ($(this).find(".list-row-check:checkbox:checked").length <= 0) {
					checked_values["sales_order"] = $(this).attr("data-so");
					checked_values["sales_order_detail"] = $(this).attr("data-so-detail");
					checked_values["customer"] = $(this).attr("data-customer");
					checked_values["company"] = $(this).attr("data-company");
					checked_values["item"] = $(this).attr("data-item");
					checked_values["qty"] = Number($(this).attr("data-qty"));
					checked_values["order_qty"] = Number($(this).attr("data-order-qty"));
					checked_values["rate"] = Number($(this).attr("data-rate"));
					checked_values["weight"] = Number($(this).attr("data-weight"));
					checked_values["route"] = $(this).attr("data-route");
					checked_values["transaction_date"] = $(this).attr("data-transaction-date");

					return checked_values;
				}
			})
			.get();
	}
};
