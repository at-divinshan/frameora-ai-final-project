import { useState } from 'react';
import AccountLayout from '../../components/layout/AccountLayout';
import { NotificationItems } from '../../components/common/NotificationBell';
import useUnreadNotifications from '../../hooks/useUnreadNotifications';
export default function Notifications(){
 const [before,setBefore]=useState(null);
 const {data,error,refresh,read}=useUnreadNotifications(before);
 return <AccountLayout><section className="account-card"><h1>Notifications</h1><button className="account-secondary" onClick={()=>{setBefore(null);refresh();}}>Refresh</button>{error&&<p role="alert">{error}</p>}{!data&&!error&&<p role="status">Loading notifications…</p>}{data&&<p>{data.unread_count} unread</p>}{data?.items.length===0&&<p>No new notifications</p>}<fieldset className="notification-list"><NotificationItems items={data?.items||[]} onRead={read}/></fieldset>{data?.next_before&&<button className="account-secondary" onClick={()=>setBefore(data.next_before)}>Older notifications</button>}{before&&<button className="account-secondary" onClick={()=>setBefore(null)}>Latest notifications</button>}</section></AccountLayout>;
}
