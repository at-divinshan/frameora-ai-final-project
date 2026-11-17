// <define:import.meta.env>
var define_import_meta_env_default = {};

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

// src/services/adminUserService.js
var getAdminUsers = (params, signal) => api_default.get("/admin/users", { params, signal }).then((r) => r.data);
var getAdminUser = (id, signal, payment_page = 1) => api_default.get(`/admin/users/${id}`, { signal, params: { payment_page } }).then((r) => r.data);
async function setAdminUserStatus(id, is_active, expected_version) {
  const { data } = await api_default.patch(`/admin/users/${id}/status`, { is_active, expected_version });
  if (data?.id !== id || data.is_active !== is_active || !Number.isInteger(data.status_version) || data.status_version < expected_version) {
    const error = new Error("Account status was not confirmed by the server. Refresh before trying again.");
    error.code = "STATUS_NOT_CONFIRMED";
    throw error;
  }
  return data;
}
function adminUserError(error) {
  if (error.code === "STATUS_NOT_CONFIRMED") return error.message;
  if (!error.response) return "Unable to reach the server. Check your connection and try again.";
  if (error.response?.status === 503 && error.response.data?.detail?.code === "ADMIN_USERS_SCHEMA_UNAVAILABLE") return "The account-status database schema is missing or incompatible. Ask the administrator to check the database configuration and migration status.";
  if (error.response?.status === 503) return "User management is temporarily unavailable. Please try again later; if this continues, ask the administrator to check the backend logs.";
  if (error.response?.status === 403) return "You do not have permission to manage this account.";
  if (error.response?.status === 409) return "The account changed. Refresh its status before trying again.";
  if (error.response?.status === 401) return "Please sign in again.";
  if (error.response?.status >= 500) return "An unexpected server error occurred. Please try again later.";
  return "Unable to load or update this account. Please try again.";
}

// src/services/googleAuthService.js
function googleErrorMessage(error) {
  if (error.response?.status === 401 && error.response.data?.detail === "This account has been deactivated. Contact the administrator.") return error.response.data.detail;
  switch (error.response?.status) {
    case 401:
      return "Unable to verify your account. Check your password or sign in again.";
    case 403:
      return "Google sign-in is not available for this account or browser origin.";
    case 409:
      return "This account cannot be created or linked. Sign in with your existing account and link Google explicitly.";
    case 422:
      return "Check your name, account type and required consent, then try again.";
    case 429:
      return "Too many attempts. Please wait a few minutes before trying again.";
    case 503:
      return "Google sign-in is currently unavailable. You can still use email and password.";
    default:
      return "Google sign-in could not be completed or has expired. Please start again.";
  }
}

// src/components/admin/UserBillingDetails.jsx
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
var value = (item) => item === null || item === void 0 || item === "" ? "Not available" : item;
var date = (item) => item ? new Date(item.endsWith("Z") ? item : `${item}Z`).toLocaleString() : "Not available";
function UserBillingDetails({ subscription, payments, onPaymentPage }) {
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx("h3", { children: "Subscription and credits" }),
    /* @__PURE__ */ jsxs("dl", { className: "account-details", children: [
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("dt", { children: "Plan" }),
        /* @__PURE__ */ jsx("dd", { children: value(subscription?.plan) })
      ] }),
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("dt", { children: "Subscription status" }),
        /* @__PURE__ */ jsx("dd", { children: value(subscription?.status) })
      ] }),
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("dt", { children: "Total allocated credits \xB7 current period" }),
        /* @__PURE__ */ jsx("dd", { children: value(subscription?.allocated) })
      ] }),
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("dt", { children: "Used credits \xB7 current period" }),
        /* @__PURE__ */ jsx("dd", { children: value(subscription?.used) })
      ] }),
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("dt", { children: "Remaining credits" }),
        /* @__PURE__ */ jsx("dd", { children: value(subscription?.remaining) })
      ] }),
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("dt", { children: "Credit period ends" }),
        /* @__PURE__ */ jsx("dd", { children: date(subscription?.period_end) })
      ] }),
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("dt", { children: "Subscription expiry" }),
        /* @__PURE__ */ jsx("dd", { children: date(subscription?.end_date) })
      ] }),
      subscription?.allowance_status && /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("dt", { children: "One-time generation allowance" }),
        /* @__PURE__ */ jsx("dd", { children: subscription.allowance_status.replaceAll("_", " ") })
      ] })
    ] }),
    subscription?.note && /* @__PURE__ */ jsx("p", { children: subscription.note }),
    /* @__PURE__ */ jsx("h3", { children: "Payment history" }),
    !payments?.available ? /* @__PURE__ */ jsx("p", { children: "Not available" }) : payments.total === 0 ? /* @__PURE__ */ jsx("p", { children: "No payment history" }) : /* @__PURE__ */ jsxs(Fragment, { children: [
      /* @__PURE__ */ jsx("p", { children: "Only recorded payment information is shown. Payment method details are not currently recorded." }),
      payments.items.length === 0 && /* @__PURE__ */ jsx("p", { children: "No payments on this page." }),
      payments.items.map((payment) => /* @__PURE__ */ jsx("article", { className: "account-card", children: /* @__PURE__ */ jsxs("dl", { className: "account-details", children: [
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("dt", { children: "Account role" }),
          /* @__PURE__ */ jsx("dd", { children: value(payment.role) })
        ] }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("dt", { children: "Subscription ID" }),
          /* @__PURE__ */ jsx("dd", { children: value(payment.subscription_id) })
        ] }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("dt", { children: "Payment provider" }),
          /* @__PURE__ */ jsx("dd", { children: value(payment.provider) })
        ] }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("dt", { children: "Payment record ID" }),
          /* @__PURE__ */ jsx("dd", { children: payment.record_id })
        ] }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("dt", { children: "Transaction ID" }),
          /* @__PURE__ */ jsx("dd", { children: value(payment.transaction_id) })
        ] }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("dt", { children: "Payment date" }),
          /* @__PURE__ */ jsx("dd", { children: date(payment.date) })
        ] }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("dt", { children: "Amount" }),
          /* @__PURE__ */ jsx("dd", { children: value(payment.amount) })
        ] }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("dt", { children: "Currency" }),
          /* @__PURE__ */ jsx("dd", { children: value(payment.currency) })
        ] }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("dt", { children: "Payment method" }),
          /* @__PURE__ */ jsx("dd", { children: value(payment.method) })
        ] }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("dt", { children: "Plan" }),
          /* @__PURE__ */ jsx("dd", { children: value(payment.plan) })
        ] }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("dt", { children: "Payment status" }),
          /* @__PURE__ */ jsx("dd", { children: value(payment.status) })
        ] })
      ] }) }, payment.record_id)),
      /* @__PURE__ */ jsxs("p", { children: [
        payments.total,
        " payments \xB7 Page ",
        payments.page
      ] }),
      /* @__PURE__ */ jsx("button", { className: "account-secondary", disabled: payments.page <= 1, onClick: () => onPaymentPage(payments.page - 1), children: "Previous payments" }),
      /* @__PURE__ */ jsx("button", { className: "account-secondary", disabled: payments.page * payments.page_size >= payments.total, onClick: () => onPaymentPage(payments.page + 1), children: "Next payments" })
    ] })
  ] });
}

// src/pages/admin/Users.jsx
import { useEffect as useEffect4, useRef as useRef2, useState as useState4 } from "react";

// src/components/layout/AdminLayout.jsx
import { useEffect as useEffect3, useState as useState3 } from "react";
import { Link, useLocation } from "react-router-dom";
import { BarChart3, Bell, Building2, CreditCard, FolderOpen, House, LogOut, Menu, Moon, Plus, Search, Settings, Sun, Users, UserRound, X } from "lucide-react";

// src/hooks/useAuth.js
import { useContext } from "react";

// src/context/AuthContext.jsx
import { createContext, useCallback, useEffect, useRef, useState } from "react";
import { jsx as jsx2 } from "react/jsx-runtime";
var AuthContext = createContext(null);

// src/components/common/AccountAvatar.jsx
import { jsx as jsx3 } from "react/jsx-runtime";

// src/context/ThemeContext.jsx
import {
  createContext as createContext2,
  useContext as useContext2,
  useEffect as useEffect2,
  useState as useState2
} from "react";
import { jsx as jsx4 } from "react/jsx-runtime";
var ThemeContext = createContext2(null);

// src/components/common/FrameoraLogo.jsx
import { jsx as jsx5, jsxs as jsxs2 } from "react/jsx-runtime";

// src/components/layout/AdminLayout.jsx
import { jsx as jsx6, jsxs as jsxs3 } from "react/jsx-runtime";

// src/pages/admin/Users.jsx
import { Fragment as Fragment2, jsx as jsx7, jsxs as jsxs4 } from "react/jsx-runtime";
function AccountSummary({ user }) {
  return /* @__PURE__ */ jsxs4("dl", { className: "account-details", children: [
    /* @__PURE__ */ jsxs4("div", { children: [
      /* @__PURE__ */ jsx7("dt", { children: "Name" }),
      /* @__PURE__ */ jsx7("dd", { children: user.name })
    ] }),
    /* @__PURE__ */ jsxs4("div", { children: [
      /* @__PURE__ */ jsx7("dt", { children: "Email" }),
      /* @__PURE__ */ jsx7("dd", { children: user.email })
    ] }),
    /* @__PURE__ */ jsxs4("div", { children: [
      /* @__PURE__ */ jsx7("dt", { children: "Role" }),
      /* @__PURE__ */ jsx7("dd", { children: user.role === "owner" ? "Studio Owner" : "Normal User" })
    ] }),
    /* @__PURE__ */ jsxs4("div", { children: [
      /* @__PURE__ */ jsx7("dt", { children: "Registered" }),
      /* @__PURE__ */ jsx7("dd", { children: new Date(user.created_at.endsWith("Z") ? user.created_at : `${user.created_at}Z`).toLocaleString() })
    ] }),
    /* @__PURE__ */ jsxs4("div", { children: [
      /* @__PURE__ */ jsx7("dt", { children: "Status" }),
      /* @__PURE__ */ jsx7("dd", { children: user.is_active ? "Active" : "Deactivated" })
    ] })
  ] });
}
export {
  AccountSummary,
  UserBillingDetails,
  adminUserError,
  api_default as api,
  getAdminUser,
  getAdminUsers,
  googleErrorMessage,
  setAdminUserStatus
};
