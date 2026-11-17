// <define:import.meta.env>
var define_import_meta_env_default = {};

// src/pages/admin/Payments.jsx
import { useEffect as useEffect4, useState as useState4 } from "react";

// src/components/layout/AdminLayout.jsx
import { useEffect as useEffect3, useState as useState3 } from "react";
import { Link, useLocation } from "react-router-dom";
import { BarChart3, Bell, Building2, CreditCard, FolderOpen, House, LogOut, Menu, Moon, Plus, Search, Settings, Sun, Users, UserRound, X } from "lucide-react";

// src/hooks/useAuth.js
import { useContext } from "react";

// src/context/AuthContext.jsx
import { createContext, useCallback, useEffect, useRef, useState } from "react";

// src/services/api.js
import axios from "axios";
var api = axios.create({
  baseURL: define_import_meta_env_default.VITE_API_URL || "http://localhost:8000",
  timeout: 3e4,
  headers: {
    "Content-Type": "application/json"
  }
});
var accessToken = null;
var unauthorizedHandler = null;
function setAccessToken(token) {
  accessToken = token;
}
api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && error.config?.headers?.Authorization === `Bearer ${accessToken}` && error.config?.url !== "/auth/login" && error.config?.url !== "/auth/google/link/start") {
      unauthorizedHandler?.();
    }
    return Promise.reject(error);
  }
);
var api_default = api;

// src/context/AuthContext.jsx
import { jsx } from "react/jsx-runtime";
var AuthContext = createContext(null);

// src/components/common/AccountAvatar.jsx
import { jsx as jsx2 } from "react/jsx-runtime";

// src/context/ThemeContext.jsx
import {
  createContext as createContext2,
  useContext as useContext2,
  useEffect as useEffect2,
  useState as useState2
} from "react";
import { jsx as jsx3 } from "react/jsx-runtime";
var ThemeContext = createContext2(null);

// src/components/common/FrameoraLogo.jsx
import { jsx as jsx4, jsxs } from "react/jsx-runtime";

// src/components/layout/AdminLayout.jsx
import { jsx as jsx5, jsxs as jsxs2 } from "react/jsx-runtime";

// src/services/adminPaymentService.js
var getAdminPayments = (params, signal) => api_default.get("/admin/payments", { params, signal }).then((r) => r.data);
var getAdminPayment = (kind, id, signal) => api_default.get(`/admin/payments/${kind}/${id}`, { signal }).then((r) => r.data);

// src/pages/admin/Payments.jsx
import { Fragment, jsx as jsx6, jsxs as jsxs3 } from "react/jsx-runtime";
var value = (v) => v ?? "Not available";
var date = (v) => v ? new Date(v.endsWith("Z") ? v : `${v}Z`).toLocaleString() : "Not available";
function formatPaymentAmount(amount, currency) {
  if (amount == null || String(amount).trim() === "" || !Number.isFinite(Number(amount))) return "Not available";
  const number = new Intl.NumberFormat("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(amount));
  return currency ? `${currency.toUpperCase()} ${number}` : `${number} (currency unavailable)`;
}
var statusLabels = { succeeded: "Succeeded", pending: "Pending", expired: "Expired", failed: "Failed", refunded: "Refunded", partially_refunded: "Partially refunded", disputed: "Disputed", review: "Review" };
function PaymentStatus({ status, checkout = false }) {
  const known = Object.hasOwn(statusLabels, status);
  return /* @__PURE__ */ jsxs3("span", { className: `payment-status payment-status--${known ? status : "unknown"}`, children: [
    known ? statusLabels[status] : value(status),
    checkout ? " checkout" : ""
  ] });
}
function PaymentSummary({ summary }) {
  return /* @__PURE__ */ jsx6("div", { className: "account-grid payment-summary", children: [["Successful sandbox payments", summary.successful], ["Sandbox revenue", formatPaymentAmount(summary.revenue, "LKR")], ["Pending payments / checkouts", summary.pending], ["Failed / refunded / disputed", summary.failed_refunded]].map(([label, n]) => /* @__PURE__ */ jsxs3("article", { className: "account-card", children: [
    /* @__PURE__ */ jsx6("h2", { children: label }),
    /* @__PURE__ */ jsx6("p", { children: value(n) })
  ] }, label)) });
}
function PaymentRows({ items, onSelect }) {
  if (!items.length) return /* @__PURE__ */ jsx6("p", { className: "account-notice payment-empty", role: "status", children: "No payment records found. Try adjusting your filters." });
  return /* @__PURE__ */ jsx6("div", { className: "payment-table-scroll", role: "region", "aria-label": "Payment transactions", tabIndex: 0, children: /* @__PURE__ */ jsxs3("table", { className: "payment-table", children: [
    /* @__PURE__ */ jsx6("caption", { className: "payment-sr-only", children: "Payment transactions \u2014 scroll horizontally to view all columns." }),
    /* @__PURE__ */ jsx6("thead", { children: /* @__PURE__ */ jsx6("tr", { children: ["Date", "Customer", "Role", "Plan", "Amount", "Status", "Stripe reference", "Details"].map((x) => /* @__PURE__ */ jsx6("th", { scope: "col", className: x === "Amount" ? "payment-amount" : void 0, children: x }, x)) }) }),
    /* @__PURE__ */ jsx6("tbody", { children: items.map((r) => /* @__PURE__ */ jsxs3("tr", { children: [
      /* @__PURE__ */ jsx6("td", { children: date(r.date) }),
      /* @__PURE__ */ jsxs3("td", { className: "payment-customer", children: [
        /* @__PURE__ */ jsx6("strong", { children: r.name }),
        /* @__PURE__ */ jsx6("span", { children: r.email })
      ] }),
      /* @__PURE__ */ jsx6("td", { children: r.role === "user" ? "Normal User" : r.role === "owner" ? "Studio Owner" : r.role }),
      /* @__PURE__ */ jsx6("td", { children: value(r.plan) }),
      /* @__PURE__ */ jsx6("td", { className: "payment-amount", children: formatPaymentAmount(r.amount, r.currency) }),
      /* @__PURE__ */ jsx6("td", { children: /* @__PURE__ */ jsx6(PaymentStatus, { status: r.status, checkout: r.kind === "checkout" }) }),
      /* @__PURE__ */ jsx6("td", { className: "payment-reference", children: value(r.transaction_id) }),
      /* @__PURE__ */ jsx6("td", { children: /* @__PURE__ */ jsx6("button", { className: "account-secondary", onClick: () => onSelect(r), children: "View Details" }) })
    ] }, `${r.kind}-${r.id}`)) })
  ] }) });
}
function PaymentDetail({ record: r }) {
  return /* @__PURE__ */ jsxs3("section", { className: "account-card payment-detail", children: [
    /* @__PURE__ */ jsx6("h2", { children: "Payment details" }),
    /* @__PURE__ */ jsxs3("p", { children: [
      r.name,
      " \xB7 ",
      r.email,
      " \xB7 ",
      r.role
    ] }),
    /* @__PURE__ */ jsxs3("p", { children: [
      "Plan: ",
      value(r.plan),
      " \xB7 Status: ",
      /* @__PURE__ */ jsx6(PaymentStatus, { status: r.status }),
      " \xB7 ",
      formatPaymentAmount(r.amount, r.currency)
    ] }),
    /* @__PURE__ */ jsxs3("p", { children: [
      "Stripe reference: ",
      value(r.transaction_id)
    ] }),
    /* @__PURE__ */ jsxs3("p", { children: [
      "Recorded verification: ",
      date(r.verified_at),
      " \xB7 Mode: ",
      r.livemode === false ? "Sandbox" : r.livemode === true ? "Live" : "Not available"
    ] }),
    /* @__PURE__ */ jsxs3("p", { children: [
      "Subscription: ",
      r.subscription ? `${r.subscription.status} \xB7 ${date(r.subscription.start_date)} \u2014 ${date(r.subscription.end_date)}` : "Not available"
    ] }),
    /* @__PURE__ */ jsxs3("p", { children: [
      "Recorded credits allocated: ",
      value(r.allocation?.credits)
    ] }),
    /* @__PURE__ */ jsxs3("p", { children: [
      "Allocation revoked: ",
      date(r.allocation?.revoked_at)
    ] }),
    /* @__PURE__ */ jsx6("h3", { children: "Recorded refund/dispute and fulfillment events" }),
    r.events.length ? /* @__PURE__ */ jsx6("ul", { children: r.events.map((e, i) => /* @__PURE__ */ jsxs3("li", { children: [
      e.event_type,
      " \xB7 ",
      e.outcome,
      " \xB7 ",
      date(e.processed_at),
      e.amount_minor != null ? ` \xB7 ${formatPaymentAmount(e.amount_minor / 100, e.currency)}` : ""
    ] }, i)) }) : /* @__PURE__ */ jsx6("p", { children: "No recorded events." })
  ] });
}
export {
  PaymentDetail,
  PaymentRows,
  PaymentStatus,
  PaymentSummary,
  api_default as api,
  formatPaymentAmount,
  getAdminPayment,
  getAdminPayments,
  setAccessToken
};
