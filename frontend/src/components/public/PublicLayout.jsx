import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { ArrowRight, Menu, Moon, Sun, X } from "lucide-react";
import FrameoraLogo from "../common/FrameoraLogo";
import useTheme from "../../hooks/useTheme";
import useAuth from "../../hooks/useAuth";
import { dashboardRoute } from "../../utils/constants";
import "../../styles/public.css";

export const publicLinks = [["/", "Home"], ["/features", "Features"], ["/how-it-works", "How It Works"], ["/for-creators", "For Creators"], ["/for-studios", "For Studios"], ["/about", "About"]];
export function StartLink({ children = "Get Started", className = "public-button" }) {
  const { user } = useAuth();
  return <Link className={className} to={user ? dashboardRoute(user.role) : "/register"}>{user ? "Open Dashboard" : children}<ArrowRight size={17} aria-hidden="true" /></Link>;
}
export default function PublicLayout() {
  const { theme, toggleTheme } = useTheme();
  const { user, loading } = useAuth();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const menuButton = useRef(null);
  const main = useRef(null);
  const previousPath = useRef(pathname);
  useEffect(() => {
    setOpen(false);
    window.scrollTo(0, 0);
    if (previousPath.current !== pathname) main.current?.focus();
    previousPath.current = pathname;
  }, [pathname]);
  return <div className="public-site">
    <a className="public-skip" href="#public-main">Skip to content</a>
    <header className="public-header public-container">
      <Link to="/" aria-label="Frameora home"><FrameoraLogo /></Link>
      <nav id="public-navigation" className={`public-nav ${open ? "is-open" : ""}`} aria-label="Main navigation" onKeyDown={event => { if (event.key === "Escape") { setOpen(false); menuButton.current?.focus(); } }}>
        {publicLinks.map(([to, label]) => <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)}>{label}</NavLink>)}
      </nav>
      <div className="public-header-actions">
        <button className="public-theme" onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}><Sun size={17} aria-hidden="true" /><Moon size={17} aria-hidden="true" /></button>
        {!loading && <Link className="public-button public-login" to={user ? dashboardRoute(user.role) : "/login"}>{user ? "Dashboard" : "Login"}<ArrowRight size={16} aria-hidden="true" /></Link>}
        <button ref={menuButton} className="public-menu" aria-label={open ? "Close navigation" : "Open navigation"} aria-expanded={open} aria-controls="public-navigation" onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
      </div>
    </header>
    <main id="public-main" ref={main} tabIndex={-1}><Outlet /></main>
    <footer className="public-footer public-container">
      <div className="public-footer-top"><div><Link to="/" aria-label="Frameora home"><FrameoraLogo /></Link><p>AI-powered inspiration.<br />Your photography journey, reimagined.</p></div><nav aria-label="Footer navigation"><h2>Explore Frameora</h2>{publicLinks.map(([to, label]) => <Link key={to} to={to}>{label}</Link>)}</nav><nav aria-label="Feature navigation"><h2>Made for your next idea</h2><Link to="/features#planning">Photography planning</Link><Link to="/features#suggestions">Creative AI guidance</Link><Link to="/features#sharing">Secure studio sharing</Link><Link to="/features#theme">Light & dark themes</Link></nav></div>
      <div className="public-footer-bottom"><span>© {new Date().getFullYear()} Frameora AI. All rights reserved.</span><span>From idea to possibility.</span></div>
    </footer>
  </div>;
}
