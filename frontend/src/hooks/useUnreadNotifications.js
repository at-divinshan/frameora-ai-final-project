import { useEffect, useRef, useState } from 'react';
import useAuth from './useAuth';
import {getNotifications,readNotification,notificationError,withoutNotifications} from '../services/notificationService';

export default function useUnreadNotifications(before=null) {
  const {user}=useAuth();
  const [data,setData]=useState(null),[error,setError]=useState(''),[,redraw]=useState(0);
  const pending=useRef(new Set()),refreshRef=useRef(()=>{});
  useEffect(()=>{
    const controller=new AbortController();let version=0;
    pending.current.clear();setData(null);setError('');
    const refresh=()=>{
      if(document.hidden || pending.current.size)return;
      const request=++version;
      getNotifications(before,controller.signal).then(result=>{
        if(!controller.signal.aborted && request===version){setData(result);setError('');}
      }).catch(e=>{if(!controller.signal.aborted && request===version)setError(notificationError(e));});
    };
    const changed=event=>{
      const {id,userId,phase,error:failure}=event.detail;
      if(userId!==user?.id)return;
      ++version; // An older inbox response must never resurrect a dismissed item.
      if(phase==='start'){pending.current.add(id);setError('');}
      else {
        if(phase==='success' && pending.current.has(id))setData(current=>withoutNotifications(current,new Set([id])));
        pending.current.delete(id);
        if(phase==='failure')setError(failure);
      }
      redraw(n=>n+1);
      // Keep failures visible, with the optimistic removal rolled back.
      if(phase==='success' && !pending.current.size)refresh();
    };
    refreshRef.current=refresh;
    window.addEventListener('notification-read',changed);window.addEventListener('focus',refresh);
    const timer=setInterval(refresh,60000);refresh();
    return()=>{++version;controller.abort();clearInterval(timer);window.removeEventListener('notification-read',changed);window.removeEventListener('focus',refresh);};
  },[user?.id,before]);
  return {data:withoutNotifications(data,pending.current),error,refresh:()=>refreshRef.current(),read:n=>readNotification(n.id,user?.id).catch(()=>{})};
}
