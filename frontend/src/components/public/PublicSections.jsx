import { useEffect } from "react";
import { ArrowRight, Camera, Plus } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { StartLink } from "./PublicLayout";
export function PageMeta({ title, description }) {
  const { hash } = useLocation();
  useEffect(() => {
    const oldTitle = document.title;
    let meta = document.querySelector('meta[name="description"]');
    const existing = !!meta;
    const oldDescription = meta?.content;
    if (!meta) { meta = document.createElement('meta'); meta.name = 'description'; document.head.appendChild(meta); }
    document.title = `${title} | Frameora AI`;
    meta.content = description;
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView();
    return () => { document.title = oldTitle; if (existing) meta.content = oldDescription; else meta.remove(); };
  }, [title, description, hash]);
  return null;
}
export function SectionHeading({ eyebrow, title, children }) {
  return <div className="public-section-heading">{eyebrow && <span className="public-eyebrow">{eyebrow}</span>}<h2>{title}</h2>{children && <p>{children}</p>}</div>;
}
export function PageHero({ eyebrow, title, accent, children }) {
  return <section className="public-page-hero public-container"><span className="public-eyebrow">{eyebrow}</span><h1>{title} <span className="public-gradient">{accent}</span></h1><p>{children}</p><StartLink /></section>;
}
export function FeatureCard({ feature, compact = false }) {
  const Icon = feature.icon;
  return <article id={compact ? undefined : feature.id} className="public-card"><span className="public-icon"><Icon size={25} aria-hidden="true" /></span><div><span className={`public-status ${feature.live ? 'live' : ''}`}>{feature.live ? 'Available' : 'Planned'}</span><h3>{compact ? feature.short || feature.title : feature.title}</h3><p>{feature.description}</p>{!compact && <p className="public-benefit">{feature.benefit}</p>}</div></article>;
}
export function FAQ({ items }) {
  return <section className="public-section public-container public-faq"><SectionHeading eyebrow="A little clarity" title="Good questions. Clear answers." /><div>{items.map(([q, a]) => <details key={q}><summary>{q}<Plus size={18} aria-hidden="true" /></summary><p>{a}</p></details>)}</div></section>;
}
export function FinalCTA({ title = 'Ready to Create Something Amazing?' }) {
  return <section className="public-container public-cta"><Camera size={40} aria-hidden="true" /><div><h2>{title}</h2><p>Bring your photography ideas to life with Frameora AI.</p></div><StartLink /><img src="/images/logo/logo-icon.png" alt="" loading="lazy" /></section>;
}
export function Timeline({ steps, title }) {
  return <section className="public-timeline"><h2>{title}</h2><ol>{steps.map(([name, description, live], i) => <li key={name}><span className="public-step-number">{String(i + 1).padStart(2, '0')}</span><div><span className={`public-status ${live ? 'live' : ''}`}>{live ? 'Available' : 'Planned'}</span><h3>{name}</h3><p>{description}</p></div></li>)}</ol></section>;
}
export function TextLink({ to, children }) { return <Link className="public-text-link" to={to}>{children}<ArrowRight size={17} aria-hidden="true" /></Link>; }
