
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Static production hosting must also supply these HTTP headers.
const securityHeaders = {
  "Content-Security-Policy": "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
  "X-Frame-Options": "DENY",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
};

export default defineConfig({
  plugins: [react()],
  preview: { headers: securityHeaders },
  server: {
    port: 5173,
    headers: securityHeaders,
  },
});
