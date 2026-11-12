import { useState } from 'react';
import { Bell } from 'lucide-react';
import { Link } from 'react-router-dom';
import useAuth from '../../hooks/useAuth';
import useUnreadNotifications from '../../hooks/useUnreadNotifications';
import { safeNotificationLink } from '../../services/notificationService';
import '../../styles/notifications.css';
export function NotificationItems({ items, onRead }) {
  return items.filter(n=>!n.is_read).map(n => <article className={`notification-item ${n.is_read ? '' : 'is-unread'}`} key={n.id}>
    <p>{n.message}</p><time dateTime={n.created_at}>{new Date(n.created_at).toLocaleString()}</time>
    <div>{safeNotificationLink(n.href) && <Link to={n.href}>View details</Link>} <button type="button" className="account-secondary" onClick={()=>onRead(n)}>Mark Read</button></div>
  </article>);
}
export default function NotificationBell({className}) {
  const {user}=useAuth();const [open,setOpen]=useState(false);
  const {data,error,refresh,read}=useUnreadNotifications();
  return <div className="notification-bell"><button className={className} type="button" aria-label={`Notifications${data?.unread_count ? `, ${data.unread_count} unread` : ''}`} aria-expanded={open} onClick={()=>{setOpen(!open);if(!open)refresh();}}><Bell size={21}/>{data?.unread_count>0 && <span className="notification-count">{data.unread_count>99?'99+':data.unread_count}</span>}</button>
    {open && <section className="notification-popover" aria-label="Recent notifications"><button className="account-secondary" onClick={()=>setOpen(false)}>Close</button><h2>Notifications</h2>{error && <p role="alert">{error}</p>}{!data&&!error&&<p role="status">Loading…</p>}{data?.items.length===0&&<p>No new notifications</p>}<NotificationItems items={data?.items.slice(0,5)||[]} onRead={read}/><Link to={`/${user.role}/notifications`} onClick={()=>setOpen(false)}>All notifications</Link></section>}
  </div>;
}
