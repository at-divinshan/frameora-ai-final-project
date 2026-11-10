import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import useAuth from '../../hooks/useAuth';
import DashboardLayout from '../../components/layout/DashboardLayout';
import OwnerLayout from '../../components/layout/OwnerLayout';
import api from '../../services/api';
import { createGuideRenderer, targetLayout, shortGuidance, groupReady, screenPoint, containRect } from '../../features/livePose/visualGuide';
import { trackGroup, supportedAnalysis } from '../../features/livePose/groupTracking';
import '../../styles/live-pose.css';

const message=(e)=>typeof e.response?.data?.detail==='string'?e.response.data.detail:e.response?.data?.detail?.message||'Unable to complete the request. Retry the same snapshot when connected.';
const EMPTY_FEEDBACK={people:[],count:0,group:{state:'neutral',guidance:'Open the camera to begin.'}};
export default function LivePoseGuide() {
  const {user}=useAuth();
  const Layout=user.role==='owner'?OwnerLayout:DashboardLayout;
  const video=useRef(null), overlay=useRef(null), stream=useRef(null), tracker=useRef(null);
  const photoTimer=useRef(null), options=useRef({visible:true,blur:true});
  const [guidanceVisible,setGuidanceVisible]=useState(true), [blurEnabled,setBlurEnabled]=useState(true);
  const [effects,setEffects]=useState({segmentation:false,blur:false}), [aspect,setAspect]=useState(4/3);
  const [stageSize,setStageSize]=useState({width:1,height:1});
  const stage=useRef(null);
  useEffect(()=>{
    const observer=new ResizeObserver(entries=>{const box=entries[0].contentRect;setStageSize({width:box.width,height:box.height});});
    if(stage.current)observer.observe(stage.current);return ()=>observer.disconnect();
  },[]);
  function changeGuidance(){
    const visible=!options.current.visible;options.current.visible=visible;setGuidanceVisible(visible);
    const c=overlay.current;if(c)c.getContext('2d').clearRect(0,0,c.width,c.height);
  }
  function changeBlur(){options.current.blur=!options.current.blur;setBlurEnabled(options.current.blur);
    const c=overlay.current;if(c)c.getContext('2d').clearRect(0,0,c.width,c.height);
  }

  const [countdown,setCountdown]=useState(0);
  const cameraEpoch=useRef(0), mounted=useRef(true), tracking=useRef(null), recommendationRef=useRef(null), expectedRef=useRef(0);
  const busyRef=useRef(false), request=useRef(null), downloadUrl=useRef(null);
  const [camera,setCamera]=useState(false), [opening,setOpening]=useState(false), [facing,setFacing]=useState('user');
  const [error,setError]=useState(''), [trackingError,setTrackingError]=useState(''), [trackLoading,setTrackLoading]=useState(false);
  const [feedback,setFeedback]=useState(EMPTY_FEEDBACK);
  const [quota,setQuota]=useState(null), [quotaError,setQuotaError]=useState('');
  const [snapshot,setSnapshot]=useState(null), [sessionId,setSessionId]=useState(null), [attempted,setAttempted]=useState(false);
  const [busy,setBusy]=useState(false), [analysis,setAnalysis]=useState(null), [suggestionIndex,setSuggestionIndex]=useState(0);
  const [rejectedScene,setRejectedScene]=useState(null);
  const [otherPhone,setOtherPhone]=useState(false), [photo,setPhoto]=useState(null);
  const refresh=()=>api.get('/live-pose/entitlements').then(({data})=>{if(mounted.current){setQuota(data);setQuotaError('');}}).catch(e=>{if(mounted.current)setQuotaError(message(e));});
  function stopCamera() {
    clearInterval(photoTimer.current);
    if(mounted.current){setCountdown(0);setTrackLoading(false);setEffects({segmentation:false,blur:false});}
    cameraEpoch.current++;
    stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;
    if(video.current) video.current.srcObject=null;
    tracking.current=null;
    if(mounted.current){setCamera(false);setOpening(false);setFeedback({...EMPTY_FEEDBACK,group:{state:'neutral',guidance:'Camera paused. Open it to resume.'}});}
  }
  useEffect(()=>{
    mounted.current=true; refresh();
    const hide=()=>{if(document.hidden)stopCamera();};
    document.addEventListener('visibilitychange',hide);
    return ()=>{mounted.current=false;stopCamera();tracker.current?.close();tracker.current=null;request.current?.abort();if(downloadUrl.current)URL.revokeObjectURL(downloadUrl.current);document.removeEventListener('visibilitychange',hide);};
  },[]);
  async function openCamera(next=facing) {
    stopCamera(); const epoch=++cameraEpoch.current;
    setOpening(true);setError('');
    try {
      if(!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error('Camera access needs HTTPS (or localhost) and a supported browser.');
      const media=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:next},width:{ideal:960},height:{ideal:720},frameRate:{ideal:24,max:30}}});
      if(!mounted.current||epoch!==cameraEpoch.current){media.getTracks().forEach(t=>t.stop());return;}
      stream.current=media;video.current.srcObject=media;await video.current.play();
      if(!mounted.current||epoch!==cameraEpoch.current)return;
      media.getVideoTracks()[0].onended=()=>{if(epoch===cameraEpoch.current)stopCamera();};
      setFacing(media.getVideoTracks()[0].getSettings().facingMode || next);setCamera(true);
    } catch(e) {
      if(mounted.current&&epoch===cameraEpoch.current){stopCamera();setError(e.name==='NotAllowedError'?'Camera permission was denied. Allow camera access in your browser settings and try again.':e.name==='NotFoundError'?'No camera was found on this device.':e.message||'Camera unavailable. Close other camera apps and retry.');}
    } finally {if(mounted.current&&epoch===cameraEpoch.current)setOpening(false);}
  }
  useEffect(()=>{
    if(!camera)return;
    let cancelled=false, frame=0, lastRun=0, lastVideo=-1, interval=150, previousAspect=null;
    const input=document.createElement('canvas');
    const render=createGuideRenderer(overlay.current);
    setTrackLoading(true);setTrackingError('');
    async function start(){
      try {
        if(!tracker.current){
          const {createTracker}=await import('../../features/livePose/tracker');
          if(cancelled)return;
          const instance=await createTracker();
          if(cancelled){instance.close();return;}
          tracker.current=instance;
        }
        setTrackLoading(false);
        const tick=(now)=>{
          if(cancelled)return;
          const v=video.current,c=overlay.current;
          // At most ~7 FPS; three scored bodies plus an overflow guard, no backlog.
          if(v&&c&&v.readyState>=2&&now-lastRun>=interval&&v.currentTime!==lastVideo){
            lastRun=now;lastVideo=v.currentTime;
            try {
              const started=performance.now(), ratio=v.videoWidth/v.videoHeight;
              if(previousAspect!==ratio){tracking.current=null;previousAspect=ratio;setAspect(ratio);}
              const scale=Math.min(1,720/Math.max(v.videoWidth,v.videoHeight));
              input.width=Math.round(v.videoWidth*scale);input.height=Math.round(v.videoHeight*scale);
              input.getContext('2d').drawImage(v,0,0,input.width,input.height);
              // The callback scopes mask ownership; no mask or frame is retained.
              tracker.current.detectForVideo(input,now,prediction=>{
                const targets=targetLayout(recommendationRef.current,ratio);
                const result=trackGroup(tracking.current,prediction.landmarks,recommendationRef.current,expectedRef.current,now,ratio,targets);
                tracking.current=result;setFeedback(result);
                let masks=[];
                try{masks=(prediction.segmentationMasks||[]).map(mask=>({width:mask.width,height:mask.height,data:mask.getAsFloat32Array()}));}catch{masks=[];}
                setEffects(render(input,masks,result,targets,options.current));
              });
              interval=Math.max(150,Math.min(500,(performance.now()-started)*2));
            }catch{setTrackingError('Pose tracking stopped. Close and reopen the camera to retry.');setFeedback({...EMPTY_FEEDBACK,group:{state:'neutral',guidance:'Tracking unavailable.'}});c.getContext('2d').clearRect(0,0,c.width,c.height);tracker.current?.close();tracker.current=null;return;}
          }
          frame=requestAnimationFrame(tick);
        };frame=requestAnimationFrame(tick);
      }catch{if(!cancelled){setTrackLoading(false);setTrackingError('Could not load the local pose model. Check your connection and reopen the camera.');}}
    }
    start();return()=>{cancelled=true;cancelAnimationFrame(frame);tracker.current?.close();tracker.current=null;tracking.current=null;const c=overlay.current;if(c)c.getContext('2d').clearRect(0,0,c.width,c.height);};
  },[camera,facing]);
  function applySuggestion(data,index){
    recommendationRef.current=data?.suggestions[index]||null;
    expectedRef.current=data?.detected_people_count||0;
    tracking.current=null;setSuggestionIndex(index);
    const c=overlay.current;if(c)c.getContext('2d').clearRect(0,0,c.width,c.height);
    setFeedback({...EMPTY_FEEDBACK,group:{state:'neutral',guidance:'Hold position while people are reassociated.'}});
  }
  function still(maxWidth=1280){
    const v=video.current;if(!v?.videoWidth||!camera)throw new Error('Wait for the camera preview.');
    const c=document.createElement('canvas');const scale=Math.min(1,maxWidth/Math.max(v.videoWidth,v.videoHeight));
    c.width=Math.round(v.videoWidth*scale);c.height=Math.round(v.videoHeight*scale);c.getContext('2d').drawImage(v,0,0,c.width,c.height);return c;
  }
  function snapshotScene(){
    try{
      setSnapshot(still(960).toDataURL('image/jpeg',.8));setSessionId(crypto.randomUUID());
      setAttempted(false);setError('');setAnalysis(null);setRejectedScene(null);applySuggestion(null,0);
    }catch(e){setError(e.message);}
  }
  async function analyze(){
    if(busyRef.current||!snapshot)return;busyRef.current=true;setBusy(true);setAttempted(true);setError('');
    const controller=new AbortController();request.current=controller;
    try{
      const {data}=await api.post('/live-pose/analyze',{session_id:sessionId,snapshot:snapshot.split(',')[1]},{signal:controller.signal,timeout:65000});
      if(!mounted.current)return;
      if(!supportedAnalysis(data))throw new Error('The response has no supported measurable targets. Retry or contact support.');
      setAnalysis(data);setSnapshot(null);setAttempted(false);applySuggestion(data,0);refresh();
    }catch(e){
      if(mounted.current){
        setError(e.response?message(e):e.message||message(e));
        const rejected=e.response?.data?.detail?.scene;
        if(rejected){setRejectedScene(rejected);setSnapshot(null);setAttempted(false);}
        // Validation/quota/conflict responses allow reframing. Gateway errors,
        // DB failures and timeouts may be ambiguous: retain the UUID for replay.
        else if([422,429,409].includes(e.response?.status))setAttempted(false);
      }
    }finally{busyRef.current=false;if(mounted.current)setBusy(false);}
  }
  function takePhoto(){
    try{still().toBlob(blob=>{if(!blob||!mounted.current)return;if(downloadUrl.current)URL.revokeObjectURL(downloadUrl.current);downloadUrl.current=URL.createObjectURL(blob);setPhoto(downloadUrl.current);},'image/jpeg',.94);}catch(e){setError(e.message);}
  }
  function delayedPhoto(){
    if(countdown)return;
    setCountdown(3);let left=3;
    photoTimer.current=setInterval(()=>{left--;setCountdown(left);if(left===0){clearInterval(photoTimer.current);takePhoto();}},1000);
  }
  const suggestion=analysis?.suggestions[suggestionIndex];
  const targets=targetLayout(suggestion,aspect);
  const rect=containRect(aspect,1,stageSize.width,stageSize.height);
  const ready=groupReady(feedback,suggestion);
  const overlayStatus=trackLoading?'Preparing guide…':busy?'Finding your pose…':!analysis?(quota?.vision_available?'Analyze to find your pose':'AI guidance is not enabled yet'):!targets.length?'Turn Phone Sideways':ready?'Perfect':feedback.count===0?'Step Into View':feedback.group.state==='red'?(/closer/i.test(feedback.group.guidance)?'Move Closer':'Give Some Space'):'Follow the silhouettes';
  return <Layout><section className="live-pose">
    <header className="live-pose-header"><h1>Live Pose Guide</h1><Link to={`/${user.role}/subscription`}>{quota?`${quota.remaining} sessions left`:'Plans'}</Link></header>
    <div ref={stage} className={`live-pose-camera ${facing==='user'?'is-mirrored':''}`}>
      <video ref={video} playsInline muted aria-label="Live camera preview" />
      <canvas ref={overlay} aria-hidden="true"/>
      {!camera&&<div className="live-pose-empty"><strong>Step into the frame</strong><button disabled={opening} onClick={()=>openCamera()}>{opening?'Opening…':'Open Camera'}</button></div>}
      {camera&&guidanceVisible&&<>
        <p className="live-pose-status" role="status">{overlayStatus}</p>
        {targets.map(target=>{
          const person=feedback.people.find(p=>p.person===target.person);
          const position=screenPoint({x:target.centerX,y:target.shoulderY-.82*target.scale},rect,facing==='user');
          return <span key={target.person} className={`live-pose-cue is-${person?.state||'neutral'}`} style={{left:position.x,top:Math.max(58,position.y)}}>{shortGuidance(person,facing==='user')}</span>;
        })}
      </>}
      {countdown>0&&<strong className="live-pose-countdown" role="status">{countdown}</strong>}
      {camera&&<button className="live-pose-hide" onClick={changeGuidance}>{guidanceVisible?'Hide guidance':'Show guidance'}</button>}
    </div>
    <div className="live-pose-controls">
      <button disabled={!camera||busy||attempted} onClick={snapshotScene}>{analysis||rejectedScene?'Reanalyze':'Analyze Scene'}</button>
      <button className="live-pose-shutter" disabled={!camera||countdown>0} onClick={delayedPhoto} aria-label="Capture photo with 3 second timer">{countdown?'Hold…':'Capture · 3s'}</button>
      <button disabled={!camera||opening} onClick={()=>openCamera(facing==='user'?'environment':'user')}>Flip</button>
    </div>
    {analysis&&<button className="live-pose-next" onClick={()=>applySuggestion(analysis,(suggestionIndex+1)%analysis.suggestions.length)}>Try next pose</button>}
    {!camera&&!quota?.vision_available&&<p className="live-pose-note" role="status">AI guidance is not enabled yet. Camera and photos are available.</p>}
    {error&&<p role="alert" className="live-pose-error">{error}</p>}
    {trackingError&&<p role="alert" className="live-pose-error">{trackingError}</p>}
    {snapshot&&<div className="live-pose-approval"><img src={snapshot} alt="Scene snapshot awaiting approval"/><div><p>Use this scene to find your pose?</p><small>One photo sent to AI. One session on success.</small><button disabled={busy||!quota?.vision_available||(!attempted&&quota?.remaining===0)} onClick={analyze}>{busy?'Analyzing…':attempted?'Retry same photo':'Approve analysis'}</button>{!quota?.vision_available&&<small>AI analysis is currently disabled.</small>}</div></div>}
    {photo&&<div className="live-pose-photo"><img src={photo} alt="Your clean captured photo"/><a href={photo} download="frameora-pose.jpg">Download photo</a></div>}
    <details className="live-pose-settings"><summary>Camera options</summary>
      <label><input type="checkbox" checked={blurEnabled} onChange={changeBlur}/> Soft background</label>
      {camera&&guidanceVisible&&blurEnabled&&!effects.blur&&<p>Background blur is unavailable until a person can be segmented reliably on this device.</p>}
      <label><input type="checkbox" checked={otherPhone} onChange={e=>setOtherPhone(e.target.checked)}/> Use another phone</label>
      {otherPhone&&<p>Keep this guide open. Your photographer can take the photo with a second phone beside this one.</p>}
      <p>Photos save without guidance or preview blur. Supports up to three people; wide groups may need landscape orientation.</p>
      <p>Position guides use approximate human proportions. Preview blur and outlines depend on real person segmentation. Mobile accuracy still needs device testing.</p>
      {quotaError&&<p>{quotaError}</p>}
      {quota&&<p>{quota.plan} · {quota.remaining} of {quota.limit} sessions available. {quota.period==='lifetime'?'Lifetime allowance.':quota.period==='trial_total'?'Trial allowance.':'Resets monthly.'}</p>}
      <button disabled={!camera} onClick={stopCamera}>Close camera</button>
    </details>
  </section></Layout>;
}
