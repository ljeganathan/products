// Interactive KOTMate demo — fully client-side, no backend calls, no data
// persisted anywhere. State resets on reload / via the Reset Demo button.
(function () {
  "use strict";

  function freshState() {
    return {
      activeArea: "billing",
      billing: { screen: "order-type", orderType: "dine-in", tableId: null, customer: 1, category: "Top Selling" },
      orders: {}, // key -> { items: [{code, qty, sentQty}] }
      tickets: [], // { id, ticketNo, orderKey, label, items:[{code,qty}], status }
      nextTicketNo: 5,
      fast: { activeField: "table", tableBuffer: "", itemBuffer: "", tableId: null, nonSeatingType: null, cart: [] },
    };
  }

  let state = freshState();

  // ---------- Helpers ----------
  function formatINR(n) {
    const rounded = Math.round(n * 100) / 100;
    const hasPaise = Math.abs(rounded - Math.round(rounded)) > 0.001;
    return (
      "₹" +
      rounded.toLocaleString("en-IN", hasPaise ? { minimumFractionDigits: 2, maximumFractionDigits: 2 } : { maximumFractionDigits: 0 })
    );
  }

  function orderKey(orderType, tableId, customer) {
    return orderType === "dine-in" ? `dinein:${tableId}:${customer}` : `nonseating:${orderType}`;
  }
  function currentOrderKey() {
    const b = state.billing;
    return orderKey(b.orderType, b.tableId, b.customer);
  }
  function getOrder(key, create) {
    if (!state.orders[key] && create) state.orders[key] = { items: [] };
    return state.orders[key];
  }
  function orderHasItems(key) {
    const o = state.orders[key];
    return !!o && o.items.some((l) => l.qty > 0);
  }
  function tableBadgeCount(tableId) {
    let n = 0;
    for (let c = 1; c <= 4; c++) if (orderHasItems(orderKey("dine-in", tableId, c))) n++;
    return n;
  }
  function computeTotals(order) {
    const lines = (order ? order.items : []).map((l) => ({ ...l, item: itemByCode(l.code) }));
    const subtotal = lines.reduce((s, l) => s + l.item.price * l.qty, 0);
    const cgst = Math.round(subtotal * 0.025 * 100) / 100;
    const sgst = Math.round(subtotal * 0.025 * 100) / 100;
    const preRound = subtotal + cgst + sgst;
    const grand = Math.round(preRound);
    const roundOff = Math.round((grand - preRound) * 100) / 100;
    return { lines, subtotal, cgst, sgst, roundOff, grand };
  }
  function currentOrderLabel() {
    const b = state.billing;
    if (b.orderType === "dine-in") {
      const t = tableById(b.tableId);
      return t ? `${t.number} · Customer-${b.customer}` : "";
    }
    return sectionById(b.orderType) ? sectionById(b.orderType).name : b.orderType;
  }

  let toastTimer = null;
  function toast(msg) {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (el.hidden = true), 2200);
  }

  function el(html) {
    const t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }

  // ---------- App actions (exposed globally for inline onclick) ----------
  const App = {};

  App.setArea = function (area) {
    state.activeArea = area;
    render();
  };

  App.selectOrderType = function (type) {
    state.billing.orderType = type;
    if (type === "dine-in") {
      state.billing.tableId = null;
    } else {
      state.billing.tableId = null;
      state.billing.customer = 1;
      state.billing.screen = "item-cart";
      state.billing.category = "Top Selling";
    }
    render();
  };

  App.selectTable = function (tableId) {
    state.billing.tableId = tableId;
    state.billing.customer = 1;
    state.billing.screen = "item-cart";
    state.billing.category = "Top Selling";
    render();
  };

  App.selectCustomer = function (n) {
    state.billing.customer = n;
    render();
  };

  App.backToOrderType = function () {
    state.billing.screen = "order-type";
    render();
  };

  App.selectCategory = function (cat) {
    state.billing.category = cat;
    render();
  };

  App.addItem = function (code) {
    const key = currentOrderKey();
    const order = getOrder(key, true);
    let line = order.items.find((l) => l.code === code);
    if (!line) {
      line = { code, qty: 0, sentQty: 0 };
      order.items.push(line);
    }
    line.qty += 1;
    render();
  };
  App.decItem = function (code) {
    const key = currentOrderKey();
    const order = getOrder(key, true);
    const line = order.items.find((l) => l.code === code);
    if (!line) return;
    line.qty = Math.max(line.sentQty, line.qty - 1); // can't drop below what's already sent to the kitchen
    render();
  };
  App.removeItem = function (code) {
    const key = currentOrderKey();
    const order = getOrder(key, true);
    order.items = order.items.filter((l) => !(l.code === code && l.sentQty === 0));
    render();
  };

  App.addToKot = function () {
    const key = currentOrderKey();
    const order = getOrder(key, true);
    const newLines = order.items.filter((l) => l.qty > l.sentQty);
    if (newLines.length === 0) {
      toast("Nothing new to send to the kitchen.");
      return;
    }
    const ticket = {
      id: "tk" + state.nextTicketNo,
      ticketNo: state.nextTicketNo++,
      orderKey: key,
      label: currentOrderLabel(),
      isSeating: state.billing.orderType === "dine-in",
      items: newLines.map((l) => ({ code: l.code, qty: l.qty - l.sentQty })),
      status: "New",
    };
    order.items.forEach((l) => (l.sentQty = l.qty));
    state.tickets.push(ticket);
    toast("Sent to kitchen ✓");
    if (state.billing.orderType === "dine-in") state.billing.screen = "order-type";
    render();
  };

  App.openBill = function () {
    const key = currentOrderKey();
    if (!orderHasItems(key)) {
      toast("Add items before billing.");
      return;
    }
    renderBillModal(key);
    document.getElementById("bill-modal-backdrop").hidden = false;
  };

  App.kotAndBill = function () {
    // Non-seating "KOT + Print Bill" — fires both together (see CLAUDE.md-style
    // Guided POS spec: takeaway/delivery pays before the food is handed over).
    const key = currentOrderKey();
    const order = getOrder(key, true);
    const newLines = order.items.filter((l) => l.qty > l.sentQty);
    if (newLines.length > 0) {
      const ticket = {
        id: "tk" + state.nextTicketNo,
        ticketNo: state.nextTicketNo++,
        orderKey: key,
        label: currentOrderLabel(),
        isSeating: false,
        items: newLines.map((l) => ({ code: l.code, qty: l.qty - l.sentQty })),
        status: "New",
        billedAlready: true,
      };
      order.items.forEach((l) => (l.sentQty = l.qty));
      state.tickets.push(ticket);
    }
    App.openBill();
  };

  App.closeBillModal = function () {
    document.getElementById("bill-modal-backdrop").hidden = true;
  };

  App.confirmBill = function (key) {
    delete state.orders[key];
    state.tickets = state.tickets.filter((t) => !(t.orderKey === key && !t.billedAlready));
    // a combined KOT+Bill ticket stays visible on the KOT screen until marked ready
    App.closeBillModal();
    toast("Bill printed ✓");
    state.billing.screen = "order-type";
    render();
  };

  App.billTicketFromKot = function (ticketId) {
    const ticket = state.tickets.find((t) => t.id === ticketId);
    if (!ticket) return;
    const parts = ticket.orderKey.split(":");
    if (parts[0] === "dinein") {
      state.billing.orderType = "dine-in";
      state.billing.tableId = parts[1];
      state.billing.customer = Number(parts[2]);
    } else {
      state.billing.orderType = parts[1];
    }
    state.billing.screen = "item-cart";
    state.activeArea = "billing";
    render();
  };

  App.markTicketReady = function (ticketId) {
    const ticket = state.tickets.find((t) => t.id === ticketId);
    if (!ticket) return;
    state.tickets = state.tickets.filter((t) => t.id !== ticketId);
    toast("Marked ready ✓");
    render();
  };

  // ---- Fast Billing ----
  App.fastSetField = function (f) {
    state.fast.activeField = f;
    render();
  };
  App.fastKey = function (d) {
    const f = state.fast;
    const key = f.activeField === "table" ? "tableBuffer" : "itemBuffer";
    if (f[key].length < 4) f[key] += d;
    render();
  };
  App.fastClear = function () {
    const f = state.fast;
    const key = f.activeField === "table" ? "tableBuffer" : "itemBuffer";
    f[key] = "";
    render();
  };
  App.fastBackspace = function () {
    const f = state.fast;
    const key = f.activeField === "table" ? "tableBuffer" : "itemBuffer";
    f[key] = f[key].slice(0, -1);
    render();
  };
  App.fastNonSeating = function (type) {
    state.fast.nonSeatingType = type;
    state.fast.tableId = null;
    state.fast.tableBuffer = "";
    state.fast.activeField = "item";
    render();
  };
  App.fastEnter = function () {
    const f = state.fast;
    if (f.activeField === "table") {
      const t = TABLES.find((tt) => tt.number.replace("T", "") === f.tableBuffer);
      if (t) {
        f.tableId = t.id;
        f.nonSeatingType = null;
        f.tableBuffer = "";
        f.activeField = "item";
      } else {
        toast("Table not found — try 1–6.");
      }
    } else {
      const item = itemByCode(f.itemBuffer);
      if (item) {
        App.fastAddItem(item.code);
        f.itemBuffer = "";
      } else {
        toast("Item code not found.");
      }
    }
    render();
  };
  App.fastAddItem = function (code) {
    const f = state.fast;
    let line = f.cart.find((l) => l.code === code);
    if (!line) {
      line = { code, qty: 0 };
      f.cart.push(line);
    }
    line.qty += 1;
    render();
  };
  App.fastDone = function () {
    const f = state.fast;
    if (!f.tableId && !f.nonSeatingType) {
      toast("Enter a table number or pick Takeaway/Online Delivery first.");
      return;
    }
    if (f.cart.length === 0) {
      toast("Add at least one item first.");
      return;
    }
    state.billing.orderType = f.tableId ? "dine-in" : f.nonSeatingType;
    state.billing.tableId = f.tableId;
    state.billing.customer = 1;
    state.billing.screen = "item-cart";
    const key = currentOrderKey();
    const order = getOrder(key, true);
    f.cart.forEach((fl) => {
      let line = order.items.find((l) => l.code === fl.code);
      if (!line) {
        line = { code: fl.code, qty: 0, sentQty: 0 };
        order.items.push(line);
      }
      line.qty += fl.qty;
    });
    state.fast = { activeField: "table", tableBuffer: "", itemBuffer: "", tableId: null, nonSeatingType: null, cart: [] };
    state.activeArea = "billing";
    render();
  };
  App.fastCancel = function () {
    state.fast = { activeField: "table", tableBuffer: "", itemBuffer: "", tableId: null, nonSeatingType: null, cart: [] };
    state.activeArea = "billing";
    render();
  };

  App.resetDemo = function () {
    state = freshState();
    render();
    toast("Demo reset ✓");
  };

  window.App = App;

  // ---------- Rendering ----------
  function render() {
    renderRail();
    document.getElementById("area-billing").hidden = state.activeArea !== "billing";
    document.getElementById("area-kot").hidden = state.activeArea !== "kot";
    document.getElementById("area-fast").hidden = state.activeArea !== "fast";
    if (state.activeArea === "billing") renderBilling();
    if (state.activeArea === "kot") renderKot();
    if (state.activeArea === "fast") renderFast();
  }

  function openTicketCount() {
    return state.tickets.length;
  }

  function renderRail() {
    const rail = document.getElementById("rail");
    rail.innerHTML = "";
    const items = [
      { area: "billing", icon: "🧾", label: "Billing" },
      { area: "kot", icon: "🎫", label: "KOT Tickets", badge: openTicketCount() },
      { area: "fast", icon: "⚡", label: "Fast Billing" },
    ];
    items.forEach((it) => {
      const btn = el(`
        <button class="rail-btn ${state.activeArea === it.area ? "is-active" : ""}" onclick="App.setArea('${it.area}')">
          <span class="icon">${it.icon}</span>
          <span>${it.label}</span>
          ${it.badge ? `<span class="rail-btn__badge">${it.badge}</span>` : ""}
        </button>
      `);
      rail.appendChild(btn);
    });
  }

  function renderBilling() {
    const root = document.getElementById("area-billing");
    root.innerHTML = "";
    if (state.billing.screen === "order-type") root.appendChild(renderOrderTypeScreen());
    else root.appendChild(renderItemCartScreen());
  }

  function renderOrderTypeScreen() {
    const wrap = el(`<div></div>`);
    wrap.appendChild(
      el(`
      <div class="screen-header">
        <div>
          <h1>${DEMO_HOTEL_NAME}</h1>
          <p>Guided POS — pick an order type to begin</p>
        </div>
      </div>
    `)
    );
    const body = el(`<div class="order-type-body"></div>`);
    const row = el(`<div class="order-type-row"></div>`);
    row.appendChild(
      el(`<button class="chip chip--dine ${state.billing.orderType === "dine-in" ? "is-selected" : ""}" onclick="App.selectOrderType('dine-in')">Dine In</button>`)
    );
    SECTIONS.filter((s) => !s.seating).forEach((s) => {
      row.appendChild(
        el(
          `<button class="chip chip--nonseating ${state.billing.orderType === s.id ? "is-selected" : ""}" onclick="App.selectOrderType('${s.id}')">${s.name}</button>`
        )
      );
    });
    body.appendChild(row);

    if (state.billing.orderType === "dine-in") {
      ["ac", "nonac"].forEach((secId) => {
        const sec = sectionById(secId);
        body.appendChild(el(`<div class="section-label">${sec.name}</div>`));
        const grid = el(`<div class="table-grid"></div>`);
        TABLES.filter((t) => t.sectionId === secId).forEach((t) => {
          const badge = tableBadgeCount(t.id);
          const tile = el(`
            <button class="table-tile ${badge > 0 ? "is-busy" : ""}" onclick="App.selectTable('${t.id}')">
              ${badge > 0 ? `<span class="table-tile__badge">${badge}</span>` : ""}
              <span class="table-tile__num">${t.number}</span>
              <span class="table-tile__seats">${t.seats} seats</span>
            </button>
          `);
          grid.appendChild(tile);
        });
        body.appendChild(grid);
      });
    }
    wrap.appendChild(body);
    return wrap;
  }

  function renderItemCartScreen() {
    const wrap = el(`<div style="height:100%;display:flex;flex-direction:column;"></div>`);
    const isDineIn = state.billing.orderType === "dine-in";
    const title = isDineIn ? `${tableById(state.billing.tableId).number} · ${sectionById(tableById(state.billing.tableId).sectionId).name}` : sectionById(state.billing.orderType).name;

    wrap.appendChild(
      el(`
      <div class="screen-header">
        <button class="back-btn" onclick="App.backToOrderType()">←</button>
        <div>
          <h1>${title}</h1>
          <p>${DEMO_HOTEL_NAME}</p>
        </div>
      </div>
    `)
    );

    const body = el(`<div class="item-cart-body"></div>`);
    const main = el(`<div class="item-cart-main"></div>`);

    if (isDineIn) {
      const custBar = el(`<div class="customer-bar"><span class="customer-bar__label">Customer</span></div>`);
      for (let c = 1; c <= 4; c++) {
        const hasOrder = orderHasItems(orderKey("dine-in", state.billing.tableId, c));
        custBar.appendChild(
          el(
            `<button class="customer-chip ${state.billing.customer === c ? "is-selected" : ""}" onclick="App.selectCustomer(${c})">C${c}${hasOrder ? " •" : ""}</button>`
          )
        );
      }
      main.appendChild(custBar);
    }

    const catNav = el(`<div class="cat-nav"></div>`);
    [...CATEGORIES, "All"].forEach((cat) => {
      catNav.appendChild(
        el(
          `<button class="cat-btn ${state.billing.category === cat ? "is-selected" : ""}" onclick="App.selectCategory('${cat}')">${cat}</button>`
        )
      );
    });
    main.appendChild(catNav);

    const grid = el(`<div class="item-grid"></div>`);
    const order = getOrder(currentOrderKey(), false);
    let items = ITEMS;
    if (state.billing.category === "Top Selling") items = ITEMS.filter((i) => i.top);
    else if (state.billing.category !== "All") items = ITEMS.filter((i) => i.category === state.billing.category);
    items.forEach((item) => {
      const line = order && order.items.find((l) => l.code === item.code);
      const qty = line ? line.qty : 0;
      const card = el(`
        <button class="item-card" onclick="App.addItem(${item.code})">
          ${qty > 0 ? `<span class="item-card__qty">${qty}</span>` : ""}
          <div class="item-card__img" style="background: hsl(${item.hue} 55% 55%);"></div>
          <div class="item-card__body">
            <div class="item-card__code">#${item.code}</div>
            <div class="item-card__name">${item.name}</div>
            <div class="item-card__ta">${item.nameTa}</div>
            <div class="item-card__price">${formatINR(item.price)}</div>
          </div>
        </button>
      `);
      grid.appendChild(card);
    });
    main.appendChild(grid);
    body.appendChild(main);
    body.appendChild(renderCartPanel(order, isDineIn));
    wrap.appendChild(body);
    return wrap;
  }

  function renderCartPanel(order, isDineIn) {
    const panel = el(`<div class="cart-panel"></div>`);
    const lines = order ? order.items.filter((l) => l.qty > 0) : [];
    panel.appendChild(
      el(`<div class="cart-header"><h2>Current Order</h2><span>${lines.length} item${lines.length === 1 ? "" : "s"}</span></div>`)
    );
    const itemsWrap = el(`<div class="cart-items"></div>`);
    if (lines.length === 0) {
      itemsWrap.appendChild(el(`<div class="cart-empty">Tap an item to add it here.</div>`));
    } else {
      lines.forEach((l) => {
        const item = itemByCode(l.code);
        const sentPart = l.sentQty > 0 ? Math.min(l.sentQty, l.qty) : 0;
        const line = el(`
          <div class="cart-line">
            <div class="cart-line__top">
              <div>
                <div class="cart-line__name">${item.name}</div>
                <div class="cart-line__ta">${item.nameTa} · ${formatINR(item.price)} each</div>
              </div>
              <div class="cart-line__amount">${formatINR(item.price * l.qty)}</div>
            </div>
            <div class="cart-line__meta">
              ${sentPart > 0 ? `<span class="cart-line__sent">Sent ×${sentPart}</span>` : "<span></span>"}
              <div class="qty-stepper">
                <button onclick="App.decItem(${l.code})">−</button>
                <span>${l.qty}</span>
                <button onclick="App.addItem(${l.code})">+</button>
              </div>
            </div>
          </div>
        `);
        itemsWrap.appendChild(line);
      });
    }
    panel.appendChild(itemsWrap);

    const totals = computeTotals(order);
    const summary = el(`
      <div class="cart-summary">
        <div class="cart-summary__row"><span>Subtotal</span><span>${formatINR(totals.subtotal)}</span></div>
        <div class="cart-summary__row total"><span>Total</span><span>${formatINR(totals.subtotal)}</span></div>
      </div>
    `);
    panel.appendChild(summary);

    const actions = el(`<div class="cart-actions"></div>`);
    const hasItems = lines.length > 0;
    const hasUnsent = lines.some((l) => l.qty > l.sentQty);
    if (isDineIn) {
      actions.appendChild(
        el(`<button class="btn-demo btn-demo--gold" ${!hasUnsent ? "disabled" : ""} onclick="App.addToKot()">🍳 Add to KOT</button>`)
      );
      actions.appendChild(el(`<button class="btn-demo btn-demo--accent" ${!hasItems ? "disabled" : ""} onclick="App.openBill()">🧾 Bill</button>`));
    } else {
      actions.appendChild(
        el(`<button class="btn-demo btn-demo--gold" ${!hasItems ? "disabled" : ""} onclick="App.kotAndBill()">🍳 KOT + Print Bill</button>`)
      );
      actions.appendChild(
        el(`<button class="btn-demo btn-demo--accent" ${!hasItems ? "disabled" : ""} onclick="App.openBill()">🧾 Bill Only (No KOT)</button>`)
      );
    }
    panel.appendChild(actions);
    return panel;
  }

  function renderBillModal(key) {
    const order = getOrder(key, false);
    const totals = computeTotals(order);
    const isDineIn = key.startsWith("dinein");
    const modal = document.getElementById("bill-modal");
    modal.innerHTML = `
      <div class="bill-receipt">
        <div class="bill-receipt__hotel">${DEMO_HOTEL_NAME}</div>
        <div class="bill-receipt__addr">${DEMO_HOTEL_ADDR}</div>
        <hr />
        <div class="bill-receipt__meta"><span>${currentOrderLabel()}</span><span>${new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}</span></div>
        <hr />
        ${totals.lines
          .map(
            (l) => `
          <div class="bill-receipt__line"><span>${l.qty} × ${l.item.name}</span><span>${formatINR(l.item.price * l.qty)}</span></div>
        `
          )
          .join("")}
        <hr />
        <div class="bill-receipt__line"><span>Subtotal</span><span>${formatINR(totals.subtotal)}</span></div>
        <div class="bill-receipt__line"><span>CGST</span><span>${formatINR(totals.cgst)}</span></div>
        <div class="bill-receipt__line"><span>SGST</span><span>${formatINR(totals.sgst)}</span></div>
        <div class="bill-receipt__line"><span>Round Off</span><span>${totals.roundOff >= 0 ? "+" : ""}${formatINR(totals.roundOff)}</span></div>
        <div class="bill-receipt__total"><span>Grand Total</span><span>${formatINR(totals.grand)}</span></div>
        <hr />
        <div class="bill-receipt__qr"></div>
        <div class="bill-receipt__thanks">Thank You &amp; Visit Again!<br />Scan to pay via UPI (demo@upi)</div>
      </div>
      <div class="bill-modal__actions">
        <button class="btn-demo" onclick="App.closeBillModal()">Cancel</button>
        <button class="btn-demo btn-demo--accent" onclick="App.confirmBill('${key}')">Confirm &amp; Print</button>
      </div>
    `;
  }

  function renderKot() {
    const root = document.getElementById("area-kot");
    root.innerHTML = "";
    root.appendChild(
      el(`
      <div class="screen-header">
        <div>
          <h1>KOT Tickets</h1>
          <p>Open kitchen tickets from any device — select one to bill it.</p>
        </div>
      </div>
    `)
    );
    const body = el(`<div class="kot-body"></div>`);
    if (state.tickets.length === 0) {
      body.appendChild(el(`<div class="ticket-empty">No open tickets right now. Send an order to the kitchen from Billing to see it here.</div>`));
    } else {
      state.tickets
        .slice()
        .reverse()
        .forEach((t) => {
          const card = el(`
          <div class="ticket-card">
            <div class="ticket-card__top">
              <div><span class="ticket-card__label">${t.label}</span>${t.billedAlready ? '<span class="ticket-card__tag">Bill printed</span>' : ""}</div>
              <span class="ticket-card__status">${t.status}</span>
            </div>
            <div class="ticket-card__id">#T${t.ticketNo}</div>
            <div class="ticket-card__items">
              ${t.items.map((l) => `<div><span>${itemByCode(l.code).name}</span><span>×${l.qty}</span></div>`).join("")}
            </div>
          </div>
        `);
          const actions = el(`<div style="display:flex;gap:8px;"></div>`);
          if (!t.billedAlready) {
            actions.appendChild(el(`<button class="btn-demo btn-demo--accent" style="flex:1;" onclick="App.billTicketFromKot('${t.id}')">Bill this ticket</button>`));
          }
          actions.appendChild(el(`<button class="btn-demo" style="flex:1;" onclick="App.markTicketReady('${t.id}')">Mark Ready</button>`));
          card.appendChild(actions);
          body.appendChild(card);
        });
    }
    root.appendChild(body);
  }

  function renderFast() {
    const root = document.getElementById("area-fast");
    root.innerHTML = "";
    root.appendChild(
      el(`
      <div class="screen-header">
        <div>
          <h1>Fast Billing</h1>
          <p>Key in table, then item codes — Enter confirms and stays ready for the next one.</p>
        </div>
      </div>
    `)
    );
    const body = el(`<div class="fast-body"></div>`);
    const main = el(`<div class="fast-main"></div>`);

    const f = state.fast;
    const tableDisplay = f.tableId ? tableById(f.tableId).number : f.nonSeatingType ? sectionById(f.nonSeatingType).name : f.tableBuffer || "—";

    main.appendChild(el(`<p class="fast-hint">No table code needed for Takeaway/Online Delivery — tap the chip instead.</p>`));

    const chips = el(`<div class="fast-chips"></div>`);
    SECTIONS.filter((s) => !s.seating).forEach((s) => {
      chips.appendChild(
        el(`<button class="chip chip--nonseating ${f.nonSeatingType === s.id ? "is-selected" : ""}" onclick="App.fastNonSeating('${s.id}')">${s.name}</button>`)
      );
    });
    main.appendChild(chips);

    const fields = el(`<div class="fast-fields"></div>`);
    fields.appendChild(
      el(`
      <div class="fast-field ${f.activeField === "table" ? "is-active" : ""}" onclick="App.fastSetField('table')">
        <span class="fast-field__label">Table</span><span class="fast-field__value">${tableDisplay}</span>
      </div>
    `)
    );
    fields.appendChild(
      el(`
      <div class="fast-field ${f.activeField === "item" ? "is-active" : ""}" onclick="App.fastSetField('item')">
        <span class="fast-field__label">Item</span><span class="fast-field__value">${f.itemBuffer || "—"}</span>
      </div>
    `)
    );
    main.appendChild(fields);

    if (f.cart.length > 0) {
      const preview = el(`<div class="fast-cart-preview"></div>`);
      f.cart.forEach((l) => {
        const item = itemByCode(l.code);
        preview.appendChild(
          el(`<div class="cart-line"><div class="cart-line__top"><div class="cart-line__name">${item.name} ×${l.qty}</div><div class="cart-line__amount">${formatINR(item.price * l.qty)}</div></div></div>`)
        );
      });
      main.appendChild(preview);
    }

    const keypad = el(`<div class="keypad"></div>`);
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "C", "0", "⌫"].forEach((k) => {
      const onclick = k === "C" ? "App.fastClear()" : k === "⌫" ? "App.fastBackspace()" : `App.fastKey('${k}')`;
      keypad.appendChild(el(`<button class="${k === "C" ? "clear" : ""}" onclick="${onclick}">${k}</button>`));
    });
    main.appendChild(keypad);

    const controls = el(`<div class="fast-controls"></div>`);
    controls.appendChild(el(`<button class="btn-demo" style="flex:1;" onclick="App.fastSetField('${f.activeField === "table" ? "item" : "table"}')">⇄ Next Field</button>`));
    controls.appendChild(el(`<button class="btn-demo btn-demo--accent" style="flex:1;" onclick="App.fastEnter()">↵ Enter</button>`));
    main.appendChild(controls);

    const doneRow = el(`<div class="fast-controls fast-done"></div>`);
    doneRow.appendChild(el(`<button class="btn-demo" style="flex:1;" onclick="App.fastCancel()">Cancel</button>`));
    doneRow.appendChild(el(`<button class="btn-demo btn-demo--accent" style="flex:2;" onclick="App.fastDone()">Done — Continue to Cart</button>`));
    main.appendChild(doneRow);

    body.appendChild(main);

    const side = el(`<div class="fast-side"><h3>Find item by name</h3></div>`);
    const search = el(`<input class="fast-search" type="text" placeholder="Search code or name…" oninput="App.fastFilter(this.value)" />`);
    side.appendChild(search);
    const list = el(`<div id="fast-side-list"></div>`);
    ITEMS.forEach((item) => {
      list.appendChild(
        el(
          `<div class="fast-side-row" data-name="${item.name.toLowerCase()}" data-code="${item.code}" onclick="App.fastAddItem(${item.code})"><span>#${item.code} ${item.name}</span><span>${formatINR(item.price)}</span></div>`
        )
      );
    });
    side.appendChild(list);
    body.appendChild(side);

    root.appendChild(body);
  }

  App.fastFilter = function (q) {
    q = q.trim().toLowerCase();
    document.querySelectorAll(".fast-side-row").forEach((row) => {
      const match = !q || row.dataset.name.includes(q) || row.dataset.code.includes(q);
      row.style.display = match ? "flex" : "none";
    });
  };

  // Reset FAB
  const fabTpl = document.getElementById("tpl-reset-fab");
  document.body.appendChild(fabTpl.content.cloneNode(true));
  document.getElementById("reset-fab").addEventListener("click", App.resetDemo);

  render();
})();
