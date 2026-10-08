/* Portal Comercial The Bulldog — frontend sem build.
 * Fala SOMENTE com a API do próprio portal (/api). Nunca com o Bling.
 * Todo texto dinâmico entra via textContent (sem innerHTML com dados).
 */
"use strict";

const state = { me: null, customer: null, catalog: null, cart: null };

// ------------------------------------------------------------------ utilidades
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
const $app = () => document.getElementById("app");
function render(...nodes) { const a = $app(); a.replaceChildren(...nodes); window.scrollTo(0, 0); }
function brl(v) { return Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }); }
function dt(iso) { return iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "-"; }
function uuid() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
  const x = [...b].map((n) => n.toString(16).padStart(2, "0")).join("");
  return `${x.slice(0, 8)}-${x.slice(8, 12)}-${x.slice(12, 16)}-${x.slice(16, 20)}-${x.slice(20)}`;
}
function toast(msg, err) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.className = "toast" + (err ? " err" : ""); t.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => { t.hidden = true; }, 3800);
}
const UNIT = { caixa: ["cx", "cx"], display: ["display", "displays"], unidade: ["un", "un"], item: ["item", "itens"] };
function uw(unit, n) { const u = UNIT[unit] || [unit, unit]; return n === 1 ? u[0] : u[1]; }
function lineUnit(line) { return line === "tabacaria" ? "display" : "caixa"; }
function shortName(name) { return (name || "").replace("The Bulldog Energy Drink ", ""); }
function groupsSummary(groups) { return groups.map((g) => `${g.paid_qty} ${uw(g.sale_unit, g.paid_qty)}`).join(" + "); }
function maskCnpj(v) {
  const d = (v || "").replace(/\D/g, "").slice(0, 14);
  return d.replace(/^(\d{2})(\d)/, "$1.$2").replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d)/, ".$1/$2").replace(/(\d{4})(\d)/, "$1-$2");
}

const STATUS = {
  recebido: ["Recebido", ""], enviado_erp: ["Em conferência", "warn"], em_conferencia: ["Em conferência", "warn"],
  aprovado: ["Aprovado", "ok"], faturado: ["Faturado", "ok"], cancelado: ["Cancelado", "err"],
};
const INTEG = { nao_requerida: ["ERP desligado", ""], pendente: ["Enviando ao Bling", "warn"], sucesso: ["No Bling", "ok"], erro: ["Erro no Bling", "err"] };
const VALID = { pendente_conferencia: ["Pendente de conferência", "warn"], conferido: ["Conferido", "ok"], rejeitado: ["Rejeitado", "err"] };
const pill = (map, key) => { const [t, c] = map[key] || [key, ""]; return h("span", { class: "pill " + c }, t); };

class ApiError extends Error { constructor(status, detail) { super(typeof detail === "string" ? detail : (detail && detail.message) || "Erro"); this.status = status; this.detail = detail; } }
async function api(method, path, body, headers) {
  const opts = { method, headers: { "X-Portal-Request": "1", ...(headers || {}) }, credentials: "same-origin" };
  if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  let res;
  try { res = await fetch("/api" + path, opts); } catch (e) { throw new ApiError(0, "Sem conexão. Verifique a internet e tente de novo."); }
  let data = null;
  try { data = await res.json(); } catch (e) { /* vazio */ }
  if (res.status === 401 && !path.startsWith("/auth/login")) { state.me = null; location.hash = "#/login"; throw new ApiError(401, "Sessão expirada."); }
  if (!res.ok) throw new ApiError(res.status, data && data.detail !== undefined ? data.detail : "Erro " + res.status);
  return data;
}
function fieldInput(label, name, attrs = {}) {
  return h("div", { class: "field" }, h("label", { for: "f-" + name }, label), h("input", { id: "f-" + name, name, ...attrs }));
}
function formData(form) { return Object.fromEntries(new FormData(form).entries()); }

// ------------------------------------------------------------------ navegação
function nav() {
  const n = document.getElementById("nav");
  if (!state.me) { n.replaceChildren(); return; }
  const r = state.me.role;
  const links = [];
  if (r === "customer") links.push(["#/pedido", "Novo pedido"], ["#/pedidos", "Meus pedidos"]);
  if (r === "seller") links.push(["#/clientes", "Clientes"], ["#/pedidos", "Pedidos"]);
  if (r === "admin") links.push(["#/pedidos", "Pedidos"], ["#/clientes", "Clientes"], ["#/admin/comercial", "Comercial"], ["#/admin/integracao", "Integração"], ["#/admin/usuarios", "Usuários"]);
  links.push(["#/conta", "Conta"]);
  const cur = location.hash.split("?")[0];
  n.replaceChildren(...links.map(([href, t]) => h("a", { href, class: cur.startsWith(href) ? "active" : "" }, t)));
}

const routes = [
  [/^#\/login$/, viewLogin, true],
  [/^#\/?$/, viewHome],
  [/^#\/pedido$/, () => viewOrder(null)],
  [/^#\/pedido\/([\w-]+)$/, (m) => viewOrder(m[1])],
  [/^#\/pedidos$/, viewOrders],
  [/^#\/pedidos\/([\w-]+)$/, (m) => viewOrderDetail(m[1])],
  [/^#\/clientes$/, viewCustomers],
  [/^#\/clientes\/novo$/, () => viewCustomerForm(null)],
  [/^#\/clientes\/([\w-]+)\/editar$/, (m) => viewCustomerForm(m[1])],
  [/^#\/clientes\/([\w-]+)$/, (m) => viewCustomer(m[1])],
  [/^#\/admin\/comercial$/, viewAdminCommercial],
  [/^#\/admin\/integracao$/, viewAdminErp],
  [/^#\/admin\/usuarios$/, viewAdminUsers],
  [/^#\/conta$/, viewAccount],
];

async function router() {
  const hash = (location.hash || "#/").split("?")[0];
  if (!state.me && hash !== "#/login") {
    try { const me = await api("GET", "/auth/me"); state.me = me.user; state.customer = me.customer || null; }
    catch (e) { location.hash = "#/login"; return; }
  }
  nav();
  for (const [re, fn] of routes) {
    const m = hash.match(re);
    if (m) {
      try { await fn(m); } catch (e) { if (e.status !== 401) render(h("div", { class: "banner err" }, e.message)); }
      nav();
      return;
    }
  }
  render(h("p", {}, "Página não encontrada."));
}
window.addEventListener("hashchange", router);
window.addEventListener("DOMContentLoaded", router);

// ------------------------------------------------------------------ login / conta
function viewLogin() {
  state.me = null; nav();
  const err = h("div", { class: "banner err hidden" });
  const form = h("form", { class: "card login", onsubmit: async (ev) => {
    ev.preventDefault();
    const d = formData(form);
    const btn = form.querySelector("button"); btn.disabled = true;
    try {
      const r = await api("POST", "/auth/login", { email: d.email, password: d.password });
      state.me = r.user; state.catalog = null; state.cart = null;
      const me = await api("GET", "/auth/me"); state.customer = me.customer || null;
      location.hash = r.user.must_change_password ? "#/conta" : "#/";
    } catch (e) { err.textContent = e.message; err.classList.remove("hidden"); }
    finally { btn.disabled = false; }
  } },
    h("img", { class: "login-logo", src: "bulldog.svg", alt: "The Bulldog" }),
    h("h1", { class: "center" }, "Entrar"),
    fieldInput("E-mail", "email", { type: "email", autocomplete: "username", required: true, autofocus: true }),
    fieldInput("Senha", "password", { type: "password", autocomplete: "current-password", required: true }),
    err,
    h("button", { class: "btn primary block", type: "submit" }, "Entrar"),
    h("p", { class: "muted small center" }, "Acesso liberado pela equipe The Bulldog.")
  );
  render(form);
}

function viewHome() {
  const r = state.me.role;
  location.hash = r === "customer" ? "#/pedido" : r === "seller" ? "#/clientes" : "#/pedidos";
}

function viewAccount() {
  const msg = h("div", { class: "banner hidden" });
  const form = h("form", { class: "card", onsubmit: async (ev) => {
    ev.preventDefault();
    const d = formData(form);
    if (d.new_password !== d.confirm) { msg.textContent = "As senhas não conferem."; msg.className = "banner err"; return; }
    try {
      await api("POST", "/auth/change-password", { current_password: d.current_password, new_password: d.new_password });
      state.me.must_change_password = false; toast("Senha alterada."); location.hash = "#/";
    } catch (e) { msg.textContent = e.message; msg.className = "banner err"; }
  } },
    state.me.must_change_password ? h("div", { class: "banner warn" }, "Defina uma senha nova para continuar.") : null,
    fieldInput("Senha atual", "current_password", { type: "password", required: true, autocomplete: "current-password" }),
    fieldInput("Nova senha (mín. 8 caracteres)", "new_password", { type: "password", required: true, minlength: 8, autocomplete: "new-password" }),
    fieldInput("Repita a nova senha", "confirm", { type: "password", required: true, minlength: 8, autocomplete: "new-password" }),
    msg,
    h("button", { class: "btn primary block", type: "submit" }, "Salvar senha")
  );
  render(
    h("h1", {}, "Minha conta"),
    h("div", { class: "card" }, h("dl", { class: "kv" }, h("dt", {}, "Nome"), h("dd", {}, state.me.name), h("dt", {}, "E-mail"), h("dd", {}, state.me.email))),
    h("h2", {}, "Trocar senha"), form,
    h("p", {}, h("button", { class: "btn block", onclick: async () => { await api("POST", "/auth/logout"); state.me = null; location.hash = "#/login"; } }, "Sair"))
  );
}

// ------------------------------------------------------------------ pedido
async function viewOrder(customerId) {
  const role = state.me.role;
  let customer;
  if (role === "customer") {
    customer = state.customer;
    if (!customer) { render(h("div", { class: "banner err" }, "Seu login não está vinculado a um cadastro. Fale com a equipe The Bulldog.")); return; }
  } else {
    if (!customerId) { location.hash = "#/clientes"; return; }
    customer = (await api("GET", "/customers/" + customerId)).customer;
  }
  const catalog = await api("GET", "/catalog" + (role === "customer" ? "" : "?customer_id=" + encodeURIComponent(customer.id)));
  if (!state.cart || state.cart.customerId !== customer.id) {
    state.cart = { customerId: customer.id, qty: {}, bonus: null, payment: catalog.payment_methods[0] ? catalog.payment_methods[0].id : null, notes: "", key: null };
  }
  const cart = state.cart;
  const summaryBox = h("div", {});
  const ctaTotal = h("div", { class: "grow" });
  const ctaBtn = h("button", { class: "btn primary", disabled: true, onclick: () => viewReview(customer, catalog) }, "Revisar pedido");
  let lastQuote = null, timer = null;

  async function refresh() {
    const items = Object.entries(cart.qty).filter(([, n]) => n > 0).map(([product_id, cases]) => ({ product_id, cases }));
    cart.key = null; // carrinho mudou: nova chave de idempotência na revisão
    if (!items.length) { lastQuote = null; summaryBox.replaceChildren(); ctaTotal.replaceChildren(h("div", { class: "muted small" }, "Escolha os produtos")); ctaBtn.disabled = true; return; }
    try {
      const r = await api("POST", "/orders/quote", { customer_id: role === "customer" ? null : customer.id, items, bonus_product_id: cart.bonus });
      lastQuote = r.quote; cart.quote = r.quote;
      summaryBox.replaceChildren(quoteBlock(r.quote, catalog, true));
      ctaTotal.replaceChildren(h("div", { class: "small muted" }, groupsSummary(r.quote.groups)), h("div", { class: "big" }, h("strong", {}, brl(r.quote.total_amount))));
      ctaBtn.disabled = false;
    } catch (e) { summaryBox.replaceChildren(h("div", { class: "banner err" }, e.message)); ctaBtn.disabled = true; }
  }
  const schedule = () => { clearTimeout(timer); timer = setTimeout(refresh, 220); };

  function stepper(p) {
    const input = h("input", { type: "number", inputmode: "numeric", min: 0, step: 1, value: cart.qty[p.id] || 0, "aria-label": (p.sale_unit === "display" ? "Displays de " : "Caixas de ") + p.short_name });
    const set = (n) => { n = Math.max(0, Math.floor(Number(n) || 0)); cart.qty[p.id] = n; input.value = n; schedule(); };
    input.addEventListener("input", () => set(input.value));
    return h("div", { class: "stepper" },
      h("button", { type: "button", "aria-label": "menos", onclick: () => set((cart.qty[p.id] || 0) - 1) }, "−"),
      input,
      h("button", { type: "button", "aria-label": "mais", onclick: () => set((cart.qty[p.id] || 0) + 1) }, "+"));
  }

  const energy = catalog.products.filter((p) => p.line === "energetico").map((p) => h("div", { class: "card product" },
    p.image_url ? h("img", { class: "prod-photo", src: p.image_url, alt: p.short_name, width: 88, height: 88 }) : h("div", { class: "can " + (p.sku.includes("ZERO") ? "zero" : "trad"), "aria-hidden": "true" }),
    h("div", { class: "info" },
      h("div", { class: "name" }, p.short_name),
      h("div", { class: "muted small" }, `Caixa com ${p.units_per_case} latas de 269 ml`),
      p.case_price ? h("div", {}, h("strong", {}, brl(p.case_price)), h("span", { class: "muted small" }, ` / caixa · ${brl(p.unit_price)} a lata`)) : h("div", { class: "banner err" }, "Sem preço configurado")),
    stepper(p)));
  const tobacco = catalog.products.filter((p) => p.line === "tabacaria").map((p) => h("div", { class: "tob-row" },
    thumb(p.image_url, "tob-photo"),
    h("div", { class: "info" },
      h("div", { class: "tob-name" }, p.short_name),
      h("div", { class: "muted small" }, `${p.sale_unit === "unidade" ? "Vendido por unidade" : `Display com ${p.pack_contents || "?"} un`} · ${p.sku.replace(/-[DU]$/, "")}`),
      p.case_price ? h("div", {}, h("strong", {}, brl(p.case_price)), h("span", { class: "muted small" }, p.sale_unit === "unidade" ? " / un" : " / display")) : h("div", { class: "banner err" }, "Sem preço configurado")),
    stepper(p)));

  const lines = (catalog.lines || []).filter((l) => catalog.products.some((p) => p.line === l.id));
  if (!cart.tab || !lines.some((l) => l.id === cart.tab)) cart.tab = lines[0] ? lines[0].id : "energetico";
  const sections = {
    energetico: h("div", { class: "line-section" }, ...energy,
      catalog.suggested_retail_price ? h("p", { class: "muted small" }, `Preço sugerido ao consumidor: ${brl(catalog.suggested_retail_price)} a lata.`) : null,
      campaignHint(catalog)),
    tabacaria: h("div", { class: "line-section" },
      h("p", { class: "muted small" }, "Smoking Line original The Bulldog Amsterdam. Venda por display fechado, exceto MaryMill e Zippo (por unidade). Preços de atacado."),
      h("div", { class: "card tob-list" }, ...tobacco)),
  };
  const tabBar = lines.length > 1 ? h("div", { class: "tabs", role: "tablist" }, ...lines.map((l) => h("button", { type: "button", role: "tab", class: "tab" + (cart.tab === l.id ? " active" : ""), "aria-selected": cart.tab === l.id ? "true" : "false", onclick: (e) => {
    cart.tab = l.id;
    for (const b of e.target.parentNode.children) { b.classList.toggle("active", b === e.target); b.setAttribute("aria-selected", b === e.target ? "true" : "false"); }
    for (const [k, el] of Object.entries(sections)) el.classList.toggle("hidden", k !== l.id);
  } }, l.label))) : null;
  for (const [k, el] of Object.entries(sections)) el.classList.toggle("hidden", k !== cart.tab);

  render(
    h("h1", {}, "Novo pedido"),
    customerHeader(customer),
    tabBar,
    ...lines.map((l) => sections[l.id]),
    summaryBox,
    h("div", { class: "sticky-cta" }, h("div", { class: "inner" }, ctaTotal, ctaBtn))
  );
  refresh();
}

function customerHeader(c) {
  return h("div", { class: "card" },
    h("div", { class: "row spread wrap" },
      h("div", {}, h("strong", {}, c.nome_fantasia || c.razao_social), h("div", { class: "muted small" }, `${c.cnpj_formatted} · ${c.municipio}/${c.uf}`)),
      c.validation_status && state.me.role !== "customer" ? pill(VALID, c.validation_status) : null));
}

function campaignHint(catalog) {
  if (!catalog.campaign) return null;
  return h("div", { class: "banner bonus" }, h("span", { class: "pill bonus" }, "CAMPANHA"), " ", `${catalog.campaign.name}: a cada ${catalog.campaign.buy_cases} caixas de energético, leve ${catalog.campaign.bonus_cases} de bônus.`);
}

function thumb(url, cls) {
  return url ? h("img", { class: cls || "thumb", src: url, alt: "", loading: "lazy", width: 40, height: 40 }) : null;
}

function itemRows(lines) {
  const rows = [];
  for (const l of lines) {
    const unit = l.sale_unit || lineUnit(l.line);
    const detail = unit === "caixa" ? `${l.cases} cx × ${brl(l.case_price)} · ${l.units} latas` : `${l.cases} ${uw(unit, l.cases)} × ${brl(l.case_price)}`;
    if (l.cases > 0) rows.push(h("tr", {}, h("td", {}, h("div", { class: "item-cell" }, thumb(l.image_url), h("div", {}, h("strong", {}, shortName(l.name)), h("div", { class: "muted small" }, detail)))), h("td", { class: "r" }, brl(l.line_total))));
    if (l.bonus_cases > 0) rows.push(h("tr", {}, h("td", {}, h("span", { class: "pill bonus" }, "BÔNUS"), " ", `${l.bonus_cases} cx ${shortName(l.name)} · ${l.bonus_units} latas`), h("td", { class: "r" }, "R$ 0,00")));
  }
  return rows;
}

function quoteBlock(q, catalog, editable) {
  const split = q.groups.length > 1;
  const rows = [];
  for (const g of q.groups) {
    if (split) rows.push(h("tr", { class: "group" }, h("td", { colspan: 2 }, g.label)));
    rows.push(...itemRows(q.lines.filter((l) => l.line === g.line)));
    if (split) rows.push(h("tr", { class: "subtotal" }, h("td", {}, "Subtotal " + g.label.split(" ")[0].toLowerCase()), h("td", { class: "r" }, brl(g.subtotal))));
  }
  rows.push(h("tr", { class: "total" }, h("td", {}, "Total"), h("td", { class: "r" }, brl(q.total_amount))));
  const counts = q.groups.map((g) => g.line === "energetico" ? `${g.paid_qty} cx pagas${g.bonus_qty ? ` + ${g.bonus_qty} de bônus` : ""} (${g.total_units} latas)` : `${g.paid_qty} ${uw(g.sale_unit, g.paid_qty)}`).join(" · ");
  const parts = [h("h2", {}, "Resumo"), h("div", { class: "card" }, h("table", { class: "summary" }, h("tbody", {}, rows)),
    h("p", { class: "muted small" }, `${counts}. Valores de tabela; impostos e condições finais são confirmados na nota fiscal.`))];
  if (split) parts.push(h("div", { class: "banner" }, `Este carrinho vira ${q.groups.length} pedidos, um por linha (energético e tabacaria), porque cada linha sai em nota fiscal própria.`));
  if (q.campaign_message) parts.push(h("div", { class: "banner " + (q.campaign_applied ? "bonus" : "") }, q.campaign_applied ? h("span", { class: "pill bonus" }, "BÔNUS") : null, " ", q.campaign_message));
  if (editable && q.bonus_cases > 0) {
    const campLine = q.campaign && q.campaign.product_line;
    const sel = h("select", { id: "f-bonus", onchange: (e) => { state.cart.bonus = e.target.value || null; window.dispatchEvent(new Event("hashchange")); } },
      h("option", { value: "" }, "Automático (sabor com mais caixas)"),
      ...catalog.products.filter((p) => !campLine || p.line === campLine).map((p) => h("option", { value: p.id, selected: state.cart.bonus === p.id }, p.short_name)));
    parts.push(h("div", { class: "field" }, h("label", { for: "f-bonus" }, "Sabor da caixa bônus"), sel));
  }
  const kv = [h("dt", {}, "Pagamento"), h("dd", {}, q.suggested_payment_terms)];
  for (const g of q.groups) kv.push(h("dt", {}, split ? "Frete " + g.label.split(" ")[0].toLowerCase() : "Frete"), h("dd", {}, g.freight_message));
  kv.push(h("dt", {}, "Prazo"), h("dd", {}, q.delivery_estimate));
  parts.push(h("div", { class: "card" }, h("dl", { class: "kv" }, ...kv)));
  return h("div", {}, ...parts);
}

function viewReview(customer, catalog) {
  const cart = state.cart, q = cart.quote;
  if (!q) return;
  if (!cart.key) cart.key = uuid(); // mesma chave em reenvios desta revisão = sem pedido duplicado
  const err = h("div", { class: "banner err hidden" });
  const payment = h("select", { id: "f-payment", onchange: (e) => { cart.payment = e.target.value; } }, ...catalog.payment_methods.map((m) => h("option", { value: m.id, selected: cart.payment === m.id }, m.label)));
  const notes = h("textarea", { id: "f-notes", maxlength: 1000, placeholder: "Ex.: entregar após 14h, falar com o gerente", oninput: (e) => { cart.notes = e.target.value; } });
  notes.value = cart.notes || "";
  const send = h("button", { class: "btn primary block", onclick: async () => {
    send.disabled = true; send.textContent = "Enviando...";
    try {
      const items = Object.entries(cart.qty).filter(([, n]) => n > 0).map(([product_id, cases]) => ({ product_id, cases }));
      const r = await api("POST", "/orders", { customer_id: state.me.role === "customer" ? null : customer.id, items, bonus_product_id: cart.bonus, payment_method: cart.payment, notes: cart.notes }, { "Idempotency-Key": cart.key });
      state.cart = null;
      viewConfirmation(r.orders || [r.order]);
    } catch (e) { err.textContent = e.message + " Você pode tentar de novo sem risco de pedido duplicado."; err.classList.remove("hidden"); send.disabled = false; send.textContent = "Confirmar e enviar pedido"; }
  } }, "Confirmar e enviar pedido");
  render(
    h("h1", {}, "Revise o pedido"),
    customerHeader(customer),
    quoteBlock(q, catalog, false),
    h("div", { class: "field" }, h("label", { for: "f-payment" }, "Meio de pagamento preferido"), payment),
    h("div", { class: "field" }, h("label", { for: "f-notes" }, "Observações"), notes),
    h("p", { class: "muted small" }, "O pedido é conferido pela equipe The Bulldog antes do faturamento. Condição de pagamento e frete são confirmados nessa etapa."),
    err, send,
    h("p", {}, h("button", { class: "btn block", onclick: () => router() }, "Voltar e alterar"))
  );
}

function viewConfirmation(orders) {
  const many = orders.length > 1;
  render(
    h("div", { class: "card center stack" },
      h("div", { class: "muted" }, many ? "Pedidos recebidos" : "Pedido recebido"),
      ...orders.map((o) => h("div", {},
        h("div", { class: "big-num" }, o.order_number),
        h("div", {}, `${many ? (o.product_line === "tabacaria" ? "Tabacaria · " : "Energético · ") : ""}${o.paid_cases} ${uw(o.sale_unit || lineUnit(o.product_line), o.paid_cases)}${o.bonus_cases ? ` + ${o.bonus_cases} de bônus` : ""} · ${brl(o.total_amount)}`))),
      h("p", { class: "muted small" }, (many ? "Guarde estes números. " : "Guarde este número. ") + "A equipe The Bulldog vai conferir e confirmar pagamento, frete e entrega.")),
    ...orders.map((o) => h("p", {}, h("a", { class: "btn primary block", href: "#/pedidos/" + o.id }, many ? `Acompanhar ${o.order_number}` : "Acompanhar pedido"))),
    h("p", {}, h("a", { class: "btn block", href: state.me.role === "customer" ? "#/pedido" : "#/clientes" }, "Fazer outro pedido"))
  );
}

// ------------------------------------------------------------------ lista / detalhe de pedidos
async function viewOrders() {
  const staff = state.me.role !== "customer";
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const filter = params.get("integration") || "";
  const data = await api("GET", "/orders" + (filter ? "?integration=" + encodeURIComponent(filter) : ""));
  const filters = staff ? h("div", { class: "row wrap" }, ...[["", "Todos"], ["erro", "Com erro no Bling"], ["pendente", "Enviando"]].map(([v, t]) => h("a", { class: "btn small" + (v === filter ? " primary" : ""), href: "#/pedidos" + (v ? "?integration=" + v : "") }, t))) : null;
  const list = data.items.length ? data.items.map((o) => h("div", { class: "card click", onclick: () => { location.hash = "#/pedidos/" + o.id; } },
    h("div", { class: "row spread" }, h("strong", {}, o.order_number), pill(STATUS, o.status)),
    staff ? h("div", {}, o.customer.nome_fantasia || o.customer.razao_social) : null,
    h("div", { class: "row spread small" }, h("span", { class: "muted" }, `${dt(o.created_at)} · ${o.product_line === "tabacaria" ? "Tabacaria" : "Energético"} · ${o.paid_cases} ${uw(o.sale_unit || lineUnit(o.product_line), o.paid_cases)}${o.bonus_cases ? " + " + o.bonus_cases + " bônus" : ""}`), h("strong", {}, brl(o.total_amount))),
    staff ? h("div", { class: "row wrap" }, pill(INTEG, o.integration_status), o.erp && o.erp.order_number ? h("span", { class: "pill" }, "Bling nº " + o.erp.order_number) : null) : null
  )) : [h("p", { class: "muted" }, "Nenhum pedido ainda.")];
  render(h("h1", {}, staff ? "Pedidos" : "Meus pedidos"), filters, ...list);
}

async function viewOrderDetail(id) {
  const { order: o } = await api("GET", "/orders/" + id);
  const staff = state.me.role !== "customer";
  const admin = state.me.role === "admin";
  const items = itemRows(o.items.map((i) => ({ ...i, line: o.product_line, sale_unit: i.sale_unit || lineUnit(o.product_line) })));
  items.push(h("tr", { class: "total" }, h("td", {}, "Total"), h("td", { class: "r" }, brl(o.total_amount))));
  const parts = [
    h("div", { class: "row spread" }, h("h1", {}, o.order_number), pill(STATUS, o.status)),
    h("p", { class: "muted" }, o.product_line === "tabacaria" ? "Tabacaria (Smoking Line)" : "Energético"),
    h("div", { class: "card" }, h("strong", {}, o.customer.nome_fantasia || o.customer.razao_social), h("div", { class: "muted small" }, `${o.customer.cnpj_formatted} · ${o.customer.municipio}/${o.customer.uf}`)),
    h("div", { class: "card" }, h("table", { class: "summary" }, h("tbody", {}, items))),
    h("div", { class: "card" }, h("dl", { class: "kv" },
      h("dt", {}, "Criado em"), h("dd", {}, dt(o.created_at)),
      h("dt", {}, "Pagamento"), h("dd", {}, `${o.suggested_payment_terms || "-"}${o.payment_method_preference ? " · preferência: " + o.payment_method_preference : ""}`),
      h("dt", {}, "Frete"), h("dd", {}, o.freight_status === "gratis" ? "Grátis" : "A combinar"),
      h("dt", {}, "Prazo"), h("dd", {}, o.delivery_estimate || "-"),
      o.notes ? h("dt", {}, "Observações") : null, o.notes ? h("dd", {}, o.notes) : null,
      o.erp && o.erp.order_number ? h("dt", {}, "Nº no Bling") : null, o.erp && o.erp.order_number ? h("dd", {}, o.erp.order_number) : null)),
  ];
  if (staff) {
    parts.push(h("h2", {}, "Integração Bling"), h("div", { class: "card stack" },
      h("div", { class: "row wrap" }, pill(INTEG, o.integration_status), o.customer_validation_at_order && o.customer_validation_at_order !== "conferido" ? pill(VALID, o.customer_validation_at_order) : null),
      o.erp ? h("div", { class: "small muted" }, `ID Bling ${o.erp.order_id}${o.erp.order_number ? " · nº " + o.erp.order_number : ""}${o.erp.status_id ? " · situação " + o.erp.status_id : ""}`) : null,
      o.integration_error ? h("div", { class: "banner err" }, o.integration_error) : null,
      admin && o.integration_status !== "sucesso" && o.integration_status !== "nao_requerida" ? h("button", { class: "btn primary", onclick: async (e) => {
        e.target.disabled = true;
        try { const r = await api("POST", `/admin/orders/${o.id}/retry`); toast(r.order.integration_status === "sucesso" ? "Enviado ao Bling." : "Ainda com erro: veja a mensagem.", r.order.integration_status !== "sucesso"); viewOrderDetail(o.id); }
        catch (err) { toast(err.message, true); e.target.disabled = false; }
      } }, "Reprocessar envio ao Bling") : null));
  }
  if (admin && o.events) {
    parts.push(h("h2", {}, "Histórico"), h("div", { class: "card" }, ...o.events.map((e) => h("div", { class: "small" }, h("span", { class: "muted" }, dt(e.at) + " · "), e.action))));
  }
  render(...parts);
}

// ------------------------------------------------------------------ clientes
async function viewCustomers() {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const q = params.get("q") || "";
  const input = h("input", { type: "search", placeholder: "Buscar por nome, fantasia, cidade ou CNPJ", value: q, "aria-label": "Buscar cliente" });
  const results = h("div", {});
  let t = null;
  async function search() {
    const data = await api("GET", "/customers" + (input.value ? "?q=" + encodeURIComponent(input.value) : ""));
    results.replaceChildren(...(data.items.length ? data.items.map((c) => h("div", { class: "card click", onclick: () => { location.hash = "#/clientes/" + c.id; } },
      h("div", { class: "row spread" }, h("strong", {}, c.nome_fantasia || c.razao_social), pill(VALID, c.validation_status)),
      h("div", { class: "muted small" }, `${c.razao_social} · ${c.cnpj_formatted}`),
      h("div", { class: "muted small" }, `${c.municipio}/${c.uf}${c.channel ? " · " + c.channel : ""}`))) : [h("p", { class: "muted" }, "Nenhum cliente encontrado.")]));
  }
  input.addEventListener("input", () => { clearTimeout(t); t = setTimeout(search, 250); });
  render(
    h("div", { class: "row spread" }, h("h1", {}, "Clientes"), h("a", { class: "btn primary small", href: "#/clientes/novo" }, "+ Novo cliente")),
    h("div", { class: "field" }, input), results);
  search();
}

async function viewCustomer(id) {
  const { customer: c } = await api("GET", "/customers/" + id);
  const admin = state.me.role === "admin";
  const kv = [["Razão social", c.razao_social], ["Fantasia", c.nome_fantasia], ["CNPJ", c.cnpj_formatted], ["IE", `${c.ie || "-"} (${c.ie_indicator_label})`], ["Contato", c.contact_name], ["Telefone", c.phone], ["WhatsApp", c.whatsapp], ["E-mail", c.email], ["E-mail NF-e", c.email_nfe],
    ["Endereço", `${c.logradouro}, ${c.numero}${c.complemento ? " - " + c.complemento : ""} · ${c.bairro} · ${c.municipio}/${c.uf} · CEP ${c.cep}`], ["Canal", c.channel]];
  const parts = [
    h("div", { class: "row spread" }, h("h1", {}, c.nome_fantasia || c.razao_social), pill(VALID, c.validation_status)),
    h("p", {}, h("a", { class: "btn primary block", href: "#/pedido/" + c.id, onclick: () => { state.cart = null; } }, "Fazer pedido para este cliente")),
    h("div", { class: "card" }, h("dl", { class: "kv" }, ...kv.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v || "-")]))),
    c.validation_notes ? h("div", { class: "banner" }, "Nota da conferência: " + c.validation_notes) : null,
    h("p", { class: "row wrap" }, h("a", { class: "btn small", href: `#/clientes/${c.id}/editar` }, "Editar cadastro"), h("a", { class: "btn small", href: "#/pedidos" }, "Ver pedidos")),
  ];
  if (admin) {
    const notes = h("input", { placeholder: "Nota (opcional)", value: c.validation_notes || "" });
    const act = (status) => async () => { try { await api("POST", `/customers/${c.id}/validation`, { status, notes: notes.value || null }); toast("Conferência registrada."); viewCustomer(c.id); } catch (e) { toast(e.message, true); } };
    parts.push(h("h2", {}, "Conferência do cadastro (back-office)"), h("div", { class: "card stack" },
      h("p", { class: "muted small" }, "Confira CNPJ, IE e endereço (Receita/Sintegra) antes de marcar como conferido. IE errada já causou rejeição de NF-e."),
      notes, h("div", { class: "row wrap" }, h("button", { class: "btn primary small", onclick: act("conferido") }, "Marcar conferido"), h("button", { class: "btn small", onclick: act("pendente_conferencia") }, "Voltar a pendente"), h("button", { class: "btn small", onclick: act("rejeitado") }, "Rejeitar"))));
  }
  render(...parts);
}

const CHANNELS = [["", "—"], ["bar", "Bar"], ["balada", "Balada"], ["tabacaria", "Tabacaria"], ["posto", "Posto de combustível"], ["mercado", "Mercado"], ["adega", "Adega"], ["distribuidor", "Distribuidor"], ["evento", "Evento"], ["outro", "Outro"]];
const UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");

async function viewCustomerForm(id) {
  const c = id ? (await api("GET", "/customers/" + id)).customer : { uf: "SP", ie_indicator: 1 };
  const err = h("div", { class: "banner err hidden" });
  const dupBox = h("div", {});
  const sel = (name, label, options, value) => h("div", { class: "field" }, h("label", { for: "f-" + name }, label), h("select", { id: "f-" + name, name }, ...options.map(([v, t]) => h("option", { value: v, selected: String(value ?? "") === String(v) }, t))));
  const cnpj = h("input", { id: "f-cnpj", name: "cnpj", required: true, inputmode: "numeric", value: c.cnpj_formatted || "", placeholder: "00.000.000/0000-00" });
  cnpj.addEventListener("input", () => { cnpj.value = maskCnpj(cnpj.value); });
  cnpj.addEventListener("blur", async () => {
    dupBox.replaceChildren();
    const d = cnpj.value.replace(/\D/g, "");
    if (d.length !== 14) return;
    const r = await api("GET", "/customers/check-cnpj?cnpj=" + d);
    if (!r.valid) dupBox.replaceChildren(h("div", { class: "banner err" }, "CNPJ inválido: confira os dígitos."));
    else if (r.exists && r.customer.id !== id) dupBox.replaceChildren(h("div", { class: "banner warn" }, "Este CNPJ já está cadastrado: ", h("a", { href: "#/clientes/" + r.customer.id }, r.customer.nome_fantasia || r.customer.razao_social), ". Use o cadastro existente."));
  });
  const ieInd = sel("ie_indicator", "Indicador de IE", [["1", "1 · Contribuinte ICMS (tem IE)"], ["2", "2 · Contribuinte isento"], ["9", "9 · Não contribuinte"]], c.ie_indicator);
  const ieField = fieldInput("Inscrição Estadual", "ie", { value: c.ie && c.ie !== "ISENTO" ? c.ie : "" });
  const syncIe = () => { const v = ieInd.querySelector("select").value; ieField.classList.toggle("hidden", v !== "1"); ieField.querySelector("input").required = v === "1"; };
  ieInd.querySelector("select").addEventListener("change", syncIe);

  const form = h("form", { class: "stack", onsubmit: async (ev) => {
    ev.preventDefault();
    err.classList.add("hidden");
    const d = formData(form);
    d.ie_indicator = Number(d.ie_indicator);
    if (d.ie_indicator !== 1) d.ie = null;
    for (const k of Object.keys(d)) if (d[k] === "") d[k] = null;
    const btn = form.querySelector("button[type=submit]"); btn.disabled = true;
    try {
      const r = id ? await api("PUT", "/customers/" + id, d) : await api("POST", "/customers", d);
      toast(id ? "Cadastro atualizado." : "Cliente cadastrado. Fica pendente de conferência pelo back-office.");
      location.hash = "#/clientes/" + r.customer.id;
    } catch (e) {
      if (e.status === 409 && e.detail && e.detail.customer) { dupBox.replaceChildren(h("div", { class: "banner warn" }, "Já existe cliente com este CNPJ: ", h("a", { href: "#/clientes/" + e.detail.customer.id }, e.detail.customer.nome_fantasia || e.detail.customer.razao_social))); dupBox.scrollIntoView(); }
      else { err.textContent = e.message; err.classList.remove("hidden"); }
      btn.disabled = false;
    }
  } },
    h("div", { class: "card" },
      h("h2", {}, "Empresa"),
      h("div", { class: "field" }, h("label", { for: "f-cnpj" }, "CNPJ"), cnpj), dupBox,
      fieldInput("Razão social", "razao_social", { required: true, value: c.razao_social || "" }),
      fieldInput("Nome fantasia", "nome_fantasia", { value: c.nome_fantasia || "" }),
      h("div", { class: "grid2" }, ieInd, ieField),
      h("p", { class: "muted small" }, "Na dúvida sobre a IE, deixe como está: o back-office confere antes do faturamento."),
      sel("channel", "Canal", CHANNELS, c.channel)),
    h("div", { class: "card" },
      h("h2", {}, "Contato"),
      fieldInput("Responsável", "contact_name", { value: c.contact_name || "" }),
      h("div", { class: "grid2" }, fieldInput("Telefone", "phone", { type: "tel", value: c.phone || "" }), fieldInput("WhatsApp", "whatsapp", { type: "tel", value: c.whatsapp || "" })),
      h("div", { class: "grid2" }, fieldInput("E-mail", "email", { type: "email", value: c.email || "" }), fieldInput("E-mail para NF-e", "email_nfe", { type: "email", required: true, value: c.email_nfe || "" }))),
    h("div", { class: "card" },
      h("h2", {}, "Endereço"),
      h("div", { class: "grid2" }, fieldInput("CEP", "cep", { required: true, inputmode: "numeric", value: c.cep || "", maxlength: 9 }), sel("uf", "UF", UFS.map((u) => [u, u]), c.uf)),
      h("div", { class: "grid3" }, fieldInput("Logradouro", "logradouro", { required: true, value: c.logradouro || "" }), fieldInput("Número", "numero", { required: true, value: c.numero || "" }), fieldInput("Complemento", "complemento", { value: c.complemento || "" })),
      h("div", { class: "grid2" }, fieldInput("Bairro", "bairro", { required: true, value: c.bairro || "" }), fieldInput("Cidade", "municipio", { required: true, value: c.municipio || "" }))),
    err,
    h("button", { class: "btn primary block", type: "submit" }, id ? "Salvar alterações" : "Cadastrar cliente"));
  render(h("h1", {}, id ? "Editar cliente" : "Novo cliente"), form);
  syncIe();
}

// ------------------------------------------------------------------ admin: comercial
async function viewAdminCommercial() {
  const p = await api("GET", "/admin/pricing");
  const cs = p.commercial_settings, camp = p.campaign || {};
  const form = h("form", { class: "stack", onsubmit: async (ev) => {
    ev.preventDefault();
    const d = formData(form);
    try {
      await api("PUT", "/admin/pricing", {
        unit_price: d.unit_price, suggested_retail_price: d.suggested_retail_price,
        campaign_active: form.querySelector("#f-camp_active").checked, campaign_name: d.campaign_name,
        campaign_buy_cases: Number(d.campaign_buy_cases), campaign_bonus_cases: Number(d.campaign_bonus_cases),
        campaign_stackable: form.querySelector("#f-camp_stack").checked, campaign_region_scope: d.campaign_region_scope,
        campaign_max_orders_per_region: d.campaign_max_orders_per_region ? Number(d.campaign_max_orders_per_region) : 0,
        commercial_settings: {
          free_freight_min_cases_home: Number(d.ff_home), free_freight_min_cases_other: Number(d.ff_other),
          delivery_estimate_home: d.de_home, delivery_estimate_other: d.de_other,
        },
      });
      toast("Configuração comercial salva.");
      viewAdminCommercial();
    } catch (e) { toast(e.message, true); }
  } },
    h("div", { class: "card" }, h("h2", {}, "Preço comercial"),
      h("div", { class: "grid2" }, fieldInput("Preço por lata (R$)", "unit_price", { required: true, inputmode: "decimal", value: p.unit_price || "" }), fieldInput("Sugerido ao consumidor (R$)", "suggested_retail_price", { inputmode: "decimal", value: p.suggested_retail_price || "" })),
      h("p", { class: "muted small" }, "Preço por caixa = preço por lata × 24. Esta é a regra COMERCIAL; o valor técnico enviado ao Bling fica em Integração.")),
    h("div", { class: "card" }, h("h2", {}, "Campanha de bônus"),
      h("label", { class: "row" }, h("input", { type: "checkbox", id: "f-camp_active", checked: camp.active !== false }), " Campanha ativa"),
      fieldInput("Nome", "campaign_name", { value: camp.name || "Lançamento 10+1" }),
      h("div", { class: "grid2" }, fieldInput("Compre (caixas)", "campaign_buy_cases", { type: "number", min: 1, value: camp.buy_cases || 10 }), fieldInput("Leve de bônus (caixas)", "campaign_bonus_cases", { type: "number", min: 1, value: camp.bonus_cases || 1 })),
      h("label", { class: "row" }, h("input", { type: "checkbox", id: "f-camp_stack", checked: camp.stackable !== false }), " Cumulativo (20 cx = 2 bônus)"),
      h("div", { class: "grid2" },
        h("div", { class: "field" }, h("label", { for: "f-scope" }, "Região da campanha"), h("select", { id: "f-scope", name: "campaign_region_scope" }, ...[["none", "Sem limite regional"], ["uf", "Por UF"], ["municipio", "Por cidade"]].map(([v, t]) => h("option", { value: v, selected: camp.region_scope === v }, t)))),
        fieldInput("Pedidos com bônus por região (vazio = sem limite)", "campaign_max_orders_per_region", { type: "number", min: 0, value: camp.max_orders_per_region || "" })),
      h("p", { class: "muted small" }, "DECISÃO PENDENTE: o brief diz \"primeiros pedidos de cada região\" sem definir quantos nem o que é região.")),
    h("div", { class: "card" }, h("h2", {}, "Frete e prazo (informativo)"),
      h("div", { class: "grid2" }, fieldInput(`Frete grátis em ${cs.home_uf} a partir de (cx)`, "ff_home", { type: "number", value: cs.free_freight_min_cases_home }), fieldInput("Fora de " + cs.home_uf + " a partir de (cx)", "ff_other", { type: "number", value: cs.free_freight_min_cases_other })),
      h("div", { class: "grid2" }, fieldInput("Prazo em " + cs.home_uf, "de_home", { value: cs.delivery_estimate_home }), fieldInput("Prazo demais estados", "de_other", { value: cs.delivery_estimate_other })),
      h("p", { class: "muted small" }, "Pagamento sugerido: " + cs.payment_terms.map((b) => `pedido ${b.from_order}${b.to_order ? (b.to_order === b.from_order ? "" : "–" + b.to_order) : "+"}: ${b.label}`).join(" · ") + ` · demais: ${cs.payment_terms_fallback}. Nada disso gera parcelas no Bling na V1.`)),
    h("button", { class: "btn primary block", type: "submit" }, "Salvar"));
  render(h("h1", {}, "Comercial"), form, await productsAdmin());
}

async function productsAdmin() {
  const data = await api("GET", "/admin/products");
  const lineChecks = data.lines.map((l) => h("label", { class: "row" }, h("input", { type: "checkbox", name: "line_" + l.id, checked: (data.enabled_lines || []).includes(l.id) }), " " + l.label));
  const rows = data.items.map((p) => h("div", { class: "prod-row" },
    h("label", { class: "row grow" }, h("input", { type: "checkbox", name: "active_" + p.id, checked: p.active }), thumb(p.image_url),
      h("span", {}, h("strong", {}, shortName(p.name)), h("span", { class: "muted small" }, ` · ${p.sku}${p.line === "tabacaria" ? (p.sale_unit === "unidade" ? " · por unidade" : p.pack_contents ? " · " + p.pack_contents + " un/display" : "") : ""}`))),
    p.line === "tabacaria" ? fieldInput(p.sale_unit === "unidade" ? "Atacado por unidade (R$)" : "Atacado por display (R$)", "price_" + p.id, { inputmode: "decimal", value: p.price || "" }) : h("p", { class: "muted small" }, "Preço do energético: definido acima (por lata).")));
  const form = h("form", { class: "card stack", onsubmit: async (ev) => {
    ev.preventDefault();
    const items = data.items.map((p) => {
      const it = { id: p.id, active: form.querySelector(`[name="active_${p.id}"]`).checked };
      if (p.line === "tabacaria") { it.price = form.querySelector(`[name="price_${p.id}"]`).value; }
      return it;
    });
    const enabled_lines = data.lines.filter((l) => form.querySelector(`[name="line_${l.id}"]`).checked).map((l) => l.id);
    try { await api("PUT", "/admin/products", { items, enabled_lines }); toast("Produtos salvos."); viewAdminCommercial(); } catch (e) { toast(e.message, true); }
  } },
    h("h2", {}, "Linhas vendidas no portal"),
    ...lineChecks,
    h("p", { class: "muted small" }, "Desmarcar a tabacaria esconde a Smoking Line do portal sem apagar preços nem pedidos."),
    h("h2", {}, "Produtos"),
    h("p", { class: "muted small" }, "Preços da tabacaria carregados do Catálogo da Distribuidora (30/09/2026)."),
    ...rows,
    h("button", { class: "btn primary block", type: "submit" }, "Salvar produtos"));
  return form;
}

// ------------------------------------------------------------------ admin: integração
async function viewAdminErp() {
  const data = await api("GET", "/admin/erp");
  if (location.hash.includes("autorizado=1")) toast("Conta Bling autorizada.");
  const blocks = data.connections.map((c) => connectionCard(c, data));
  const newForm = h("form", { class: "card stack", onsubmit: async (ev) => {
    ev.preventDefault(); const d = formData(newForm);
    try { await api("POST", "/admin/erp/connections", { label: d.label, mode: "disabled", credentials_env_prefix: d.prefix || null }); toast("Conexão criada."); viewAdminErp(); } catch (e) { toast(e.message, true); }
  } }, h("h2", {}, "Nova conexão"), fieldInput("Nome", "label", { required: true }), fieldInput("Prefixo das credenciais no servidor (ex.: BLING_DFJ)", "prefix", { pattern: "[A-Z][A-Z0-9_]*" }), h("button", { class: "btn", type: "submit" }, "Criar"));
  render(h("h1", {}, "Integração Bling"),
    h("div", { class: "banner" }, "O portal cria apenas PEDIDOS no Bling (sem NF-e, sem contas a receber, sem estoque). Só uma conexão fica ativa. Credenciais ficam no servidor; esta tela nunca mostra tokens."),
    ...blocks, newForm,
    h("p", {}, h("button", { class: "btn block", onclick: async () => { const r = await api("POST", "/admin/jobs/process"); toast(`${r.processed} envio(s) processado(s).`); } }, "Processar fila de envios agora")));
}

function connectionCard(c, data) {
  const s = c.settings;
  const prodInputs = data.products.map((p) => fieldInput(`ID Bling — ${p.sku}`, "prod_" + p.id, { inputmode: "numeric", value: c.product_external_ids[p.id] || "" }));
  const sellerInputs = data.sellers.map((u) => fieldInput(`ID vendedor Bling — ${u.name}`, "seller_" + u.id, { inputmode: "numeric", value: c.seller_external_ids[u.id] || "" }));
  const overrides = data.products.map((p) => fieldInput(`Valor técnico por lata — ${p.sku}`, "ovr_" + p.sku, { inputmode: "decimal", value: (s.technical_unit_price_overrides || {})[p.sku] || "" }));
  const sel = (name, label, opts, val) => h("div", { class: "field" }, h("label", { for: `f-${c.id}-${name}` }, label), h("select", { id: `f-${c.id}-${name}`, name }, ...opts.map(([v, t]) => h("option", { value: v, selected: String(val ?? "") === String(v) }, t))));
  const form = h("form", { class: "stack", onsubmit: async (ev) => {
    ev.preventDefault();
    const d = formData(form);
    const pick = (prefix) => Object.fromEntries(Object.entries(d).filter(([k]) => k.startsWith(prefix)).map(([k, v]) => [k.slice(prefix.length), v || null]));
    try {
      await api("PUT", "/admin/erp/connections/" + c.id, {
        label: d.label, mode: d.mode, credentials_env_prefix: d.prefix || null,
        settings: {
          order_initial_status_id: d.order_initial_status_id || null, store_id: d.store_id || null, operation_nature_id: d.operation_nature_id || null,
          warehouse_id: d.warehouse_id || null, freight_payer_code: d.freight_payer_code === "" ? null : d.freight_payer_code, contact_type_customer_id: d.contact_type_customer_id || null,
          technical_price_mode: d.technical_price_mode, technical_unit_price_overrides: pick("ovr_"),
          bonus_line_mode: d.bonus_line_mode, bonus_technical_unit_value: d.bonus_technical_unit_value || "0",
          send_pending_customers: form.querySelector(`#f-${c.id}-spc`).checked,
        },
        product_external_ids: pick("prod_"), seller_external_ids: pick("seller_"),
      });
      toast("Conexão salva."); viewAdminErp();
    } catch (e) { toast(e.message, true); }
  } },
    h("div", { class: "grid2" }, fieldInput("Nome", "label", { value: c.label }), sel("mode", "Modo", [["disabled", "Desligada (pedido só no portal)"], ["mock", "Simulada (testes, sem Bling)"], ["bling", "Bling real"]], c.mode)),
    fieldInput("Prefixo das credenciais no servidor", "prefix", { value: c.credentials_env_prefix || "", pattern: "[A-Z][A-Z0-9_]*" }),
    h("h2", {}, "Produtos e vendedores"), ...prodInputs, ...sellerInputs,
    h("h2", {}, "Pedido no Bling"),
    h("div", { class: "grid2" }, fieldInput("Situação inicial (ID)", "order_initial_status_id", { inputmode: "numeric", value: s.order_initial_status_id ?? "" }), fieldInput("Loja (ID, opcional)", "store_id", { inputmode: "numeric", value: s.store_id ?? "" })),
    h("div", { class: "grid2" }, fieldInput("Natureza de operação (ID) — PENDENTE DFJ", "operation_nature_id", { inputmode: "numeric", value: s.operation_nature_id ?? "" }), fieldInput("Depósito (ID) — PENDENTE DFJ", "warehouse_id", { inputmode: "numeric", value: s.warehouse_id ?? "" })),
    h("div", { class: "grid2" }, sel("freight_payer_code", "Frete por conta — PENDENTE DFJ", [["", "Não enviar"], ["0", "0 · Remetente (CIF)"], ["1", "1 · Destinatário (FOB)"], ["2", "2 · Terceiros"], ["3", "3 · Próprio remetente"], ["4", "4 · Próprio destinatário"], ["9", "9 · Sem frete"]], s.freight_payer_code), fieldInput("Tipo de contato 'Cliente' (ID)", "contact_type_customer_id", { inputmode: "numeric", value: s.contact_type_customer_id ?? "" })),
    h("h2", {}, "Valor técnico enviado ao item"),
    sel("technical_price_mode", "Modo", [["commercial", "Igual ao preço comercial por lata"], ["override", "Valor definido por SKU"]], s.technical_price_mode), ...overrides,
    h("div", { class: "grid2" }, sel("bonus_line_mode", "Caixa bônus", [["separate_item", "Item separado no pedido"], ["observation_only", "Só nas observações"]], s.bonus_line_mode), fieldInput("Valor técnico por lata do bônus", "bonus_technical_unit_value", { inputmode: "decimal", value: s.bonus_technical_unit_value })),
    h("label", { class: "row" }, h("input", { type: "checkbox", id: `f-${c.id}-spc`, checked: s.send_pending_customers }), " Enviar pedidos de clientes ainda pendentes de conferência"),
    h("button", { class: "btn primary block", type: "submit" }, "Salvar conexão"));
  return h("div", { class: "card stack" },
    h("div", { class: "row spread wrap" }, h("strong", {}, c.label), h("div", { class: "row wrap" }, c.is_active ? h("span", { class: "pill ok" }, "ATIVA") : h("span", { class: "pill" }, "inativa"), h("span", { class: "pill" }, c.mode), c.mode === "bling" ? (c.authorized ? h("span", { class: "pill ok" }, "autorizada") : h("span", { class: "pill err" }, "não autorizada")) : null)),
    c.pending_for_dfj.length ? h("div", { class: "banner warn small" }, "Ainda sem definição: " + c.pending_for_dfj.join(", ")) : null,
    h("div", { class: "row wrap" },
      !c.is_active ? h("button", { class: "btn small", onclick: async () => { await api("POST", `/admin/erp/connections/${c.id}/activate`); toast("Conexão ativada."); viewAdminErp(); } }, "Tornar ativa") : null,
      c.mode === "bling" ? h("button", { class: "btn small", onclick: async () => { try { const r = await api("GET", `/admin/erp/connections/${c.id}/oauth/start`); location.href = r.url; } catch (e) { toast(e.message, true); } } }, c.authorized ? "Reautorizar no Bling" : "Conectar ao Bling") : null,
      c.mode !== "disabled" ? h("button", { class: "btn small", onclick: async () => { try { const r = await api("POST", `/admin/erp/connections/${c.id}/sync-status`); toast(`${r.changed} pedido(s) atualizados.`); } catch (e) { toast(e.message, true); } } }, "Sincronizar status") : null),
    h("details", {}, h("summary", {}, "Configurar"), form));
}

// ------------------------------------------------------------------ admin: usuários
async function viewAdminUsers() {
  const data = await api("GET", "/admin/users");
  const customers = (await api("GET", "/customers")).items;
  const custSel = h("div", { class: "field hidden" }, h("label", { for: "f-customer_id" }, "Cliente (PDV)"), h("select", { id: "f-customer_id", name: "customer_id" }, h("option", { value: "" }, "—"), ...customers.map((c) => h("option", { value: c.id }, `${c.nome_fantasia || c.razao_social} · ${c.cnpj_formatted}`))));
  const role = h("select", { id: "f-role", name: "role", onchange: () => custSel.classList.toggle("hidden", role.value !== "customer") }, h("option", { value: "seller" }, "Vendedor"), h("option", { value: "customer" }, "Cliente / PDV"), h("option", { value: "admin" }, "Admin (back-office)"));
  const form = h("form", { class: "card stack", onsubmit: async (ev) => {
    ev.preventDefault(); const d = formData(form);
    try {
      await api("POST", "/admin/users", { role: d.role, name: d.name, email: d.email, password: d.password, customer_id: d.role === "customer" ? d.customer_id || null : null, seller_type: d.role === "seller" ? d.seller_type || null : null });
      toast("Usuário criado. A pessoa troca a senha no primeiro acesso."); viewAdminUsers();
    } catch (e) { toast(e.message, true); }
  } },
    h("h2", {}, "Novo usuário"),
    h("div", { class: "field" }, h("label", { for: "f-role" }, "Perfil"), role), custSel,
    fieldInput("Nome", "name", { required: true }), fieldInput("E-mail", "email", { type: "email", required: true }),
    fieldInput("Senha provisória (mín. 8)", "password", { type: "text", required: true, minlength: 8 }),
    fieldInput("Tipo de vendedor (ex.: dfj, st_nicolas)", "seller_type", {}),
    h("button", { class: "btn primary", type: "submit" }, "Criar usuário"));
  const roleName = { admin: "Admin", seller: "Vendedor", customer: "Cliente/PDV" };
  render(h("h1", {}, "Usuários"), ...data.items.map((u) => h("div", { class: "card row spread wrap" },
    h("div", {}, h("strong", {}, u.name), h("div", { class: "muted small" }, `${u.email} · ${roleName[u.role]}${u.seller_type ? " · " + u.seller_type : ""}`)),
    u.id === state.me.id ? h("span", { class: "pill" }, "você") : h("button", { class: "btn small", onclick: async () => { await api("PATCH", "/admin/users/" + u.id, { active: !u.active }); viewAdminUsers(); } }, u.active ? "Desativar" : "Reativar"))), form);
}
