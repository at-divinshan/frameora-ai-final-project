import { POSES } from './poses.js';
const templates=Object.fromEntries(POSES.map(p=>[p.id,p]));

// A composition guide, not a segmentation result. Targets are projected from the
// SAME normalized joints used for scoring; never fabricate targets without AI.
export function targetLayout(recommendation,aspect) {
  const people=recommendation?.people;
  if(!Number.isFinite(aspect)||aspect<=0||!people?.length||people.length>3||people.some(p=>!templates[p.pose_id])||new Set(people.map(p=>p.person)).size!==people.length||people.some(p=>!Number.isInteger(p.person)||p.person<1||p.person>people.length))return [];
  const gap={close:1.7,comfortable:2.5,wide:4,none:2.5}[recommendation.spacing];
  if(!gap)return [];
  const extent=Math.max(...people.flatMap(p=>Object.values(templates[p.pose_id].points).map(([x])=>Math.abs(x))))+.2;
  const scale=Math.min(.19,.86*aspect/(2*extent+gap*(people.length-1)));
  if(scale<.085)return []; // Too small for reliable full-body matching; rotate/reframe.
  const shoulderY=.5-1.1*scale;
  return [...people].sort((a,b)=>a.person-b.person).map((p,i)=>{
    const centerX=.5+(i-(people.length-1)/2)*gap*scale/aspect;
    const points=Object.fromEntries(Object.entries(templates[p.pose_id].points).map(([key,[x,y]])=>[key,{x:centerX+x*scale/aspect,y:shoulderY+y*scale}]));
    return {...p,centerX,shoulderY,scale,points,hip:{x:centerX,y:shoulderY+scale}};
  });
}
export function positionMatch(geometry,target,aspect){
  if(!geometry||!target)return {matches:false,guidance:'Find Your Mark'};
  const dx=(geometry.x-target.hip.x*aspect)/target.scale;
  const dy=(geometry.y-target.hip.y)/target.scale;
  const ratio=geometry.scale/target.scale;
  if(Math.abs(dx)>.3)return {matches:false,guidance:dx>0?'Move Left':'Move Right'};
  if(ratio<.75)return {matches:false,guidance:'Step Closer'};
  if(ratio>1.25)return {matches:false,guidance:'Step Back'};
  if(Math.abs(dy)>.35)return {matches:false,guidance:dy>0?'Move Up':'Move Down'};
  return {matches:true,guidance:'Hold Pose'};
}
export function shortGuidance(person,mirrored=false){
  let text=person?.guidance||'Step Into View';
  if(person?.state==='green')return 'Perfect';
  if(person?.state==='neutral')return 'Step Into View';
  if(/^[A-Z][a-z]+ (Left|Right|Up|Down|Closer|Back)$/.test(text)){
    if(mirrored)text=text==='Move Left'?'Move Right':text==='Move Right'?'Move Left':text;
    return text;
  }
  if(/hip/i.test(text))return 'Hand on Hip';
  if(/Extend/i.test(text))return 'Raise Hand';
  if(/Lower/i.test(text))return 'Lower Hand';
  if(/upright|facing/i.test(text))return 'Face Camera';
  return 'Hold Pose';
}
export function groupReady(result,rec){
  return !!rec&&result.people.length===rec.people.length&&result.people.every(p=>p.state==='green')&&(rec.people.length===1||rec.spacing==='none'||result.group.state==='green');
}
export function guideLayers(visible,blur,masksAvailable){
  return {targets:visible,outlines:visible&&masksAvailable,blur:visible&&blur&&masksAvailable};
}
// One contain transform for all video/canvas layers. No object-fit cropping.
export function containRect(vw,vh,w,h){const scale=Math.min(w/vw,h/vh);return {x:(w-vw*scale)/2,y:(h-vh*scale)/2,width:vw*scale,height:vh*scale};}
export function screenPoint(point,rect,mirrored){return {x:rect.x+(mirrored?1-point.x:point.x)*rect.width,y:rect.y+point.y*rect.height};}

// Downsample REAL per-pose segmentation probabilities. Return union opacity and
// per-person contour pixels. Never infer a body boundary from skeleton joints.
export function maskPixels(masks,states,w,h){
  const union=new Uint8ClampedArray(w*h*4),edges=new Uint8ClampedArray(w*h*4);
  if(!masks.length)return {union,edges};
  const grids=masks.map(m=>{
    const grid=new Uint8Array(w*h);
    for(let y=0;y<h;y++)for(let x=0;x<w;x++){
      const value=m.data[Math.min(m.height-1,Math.floor(y*m.height/h))*m.width+Math.min(m.width-1,Math.floor(x*m.width/w))];
      grid[y*w+x]=Number.isFinite(value)&&value>=.55?1:0;
    }return grid;
  });
  const colors={green:[50,230,152],red:[255,83,95],neutral:[180,191,208]};
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){
    const i=y*w+x,owners=[];
    grids.forEach((g,k)=>{if(g[i])owners.push(k);});
    if(!owners.length)continue;
    union[i*4+3]=255;
    for(const owner of owners){
      const g=grids[owner];
      if(x>0&&x<w-1&&y>0&&y<h-1&&g[i-1]&&g[i+1]&&g[i-w]&&g[i+w])continue;
      const color=colors[owners.length>1?'neutral':states[owner]]||colors.neutral;
      edges.set([...color,255],i*4);
    }
  }
  return {union,edges};
}
export function usableMasks(masks,result){
  return masks.length===result.count&&masks.length>0&&masks.every((m,i)=>{
    if(!(m.width>0&&m.height>0&&m.data?.length===m.width*m.height))return false;
    let area=0;
    for(const value of m.data){if(!Number.isFinite(value)||value<0||value>1)return false;if(value>=.55)area++;}
    if(area<m.data.length*.003||area>m.data.length*.9)return false;
    const person=result.people.find(p=>p.detectionIndex===i);
    const hip=person?.points?.[23];
    if(hip&&Number.isFinite(hip.x)&&Number.isFinite(hip.y)&&hip.x>=0&&hip.x<1&&hip.y>=0&&hip.y<1){
      if(m.data[Math.floor(hip.y*m.height)*m.width+Math.floor(hip.x*m.width)]<.55)return false;
    }
    return true;
  });
}
export function createGuideRenderer(canvas,makeCanvas=()=>document.createElement('canvas')){
  const matte=makeCanvas(),foreground=makeCanvas(),contour=makeCanvas(),ghost=makeCanvas();
  return (frame,masks,result,targets,{visible,blur})=>{
    const w=frame.width,h=frame.height;canvas.width=w;canvas.height=h;
    const ctx=canvas.getContext('2d');ctx.clearRect(0,0,w,h);
    const available=usableMasks(masks,result);
    const layers=guideLayers(visible,blur,available);
    if(!visible)return {segmentation:available,blur:false};
    if(layers.outlines){
      const mw=Math.min(192,w),mh=Math.max(1,Math.round(mw*h/w));
      const states=masks.map((_,i)=>result.people.find(p=>p.detectionIndex===i)?.state||'neutral');
      const {union,edges}=maskPixels(masks,states,mw,mh);
      matte.width=contour.width=mw;matte.height=contour.height=mh;
      for(const [surface,data] of [[matte,union],[contour,edges]]){
        const c=surface.getContext('2d'),pixels=c.createImageData(mw,mh);pixels.data.set(data);c.putImageData(pixels,0,0);
      }
      if(layers.blur&&'filter' in ctx){
        ctx.filter='blur(3px)';ctx.drawImage(frame,0,0,w,h);ctx.filter='none';
        foreground.width=w;foreground.height=h;
        const fg=foreground.getContext('2d');fg.drawImage(frame,0,0,w,h);
        fg.globalCompositeOperation='destination-in';fg.drawImage(matte,0,0,w,h);fg.globalCompositeOperation='source-over';
        ctx.drawImage(foreground,0,0);
      }
    }
    if(layers.targets){
      ghost.width=w;ghost.height=h;
      const g=ghost.getContext('2d');g.fillStyle='#d9d2ff';
      for(const target of targets)drawSilhouette(g,target,w,h);
      ctx.globalAlpha=.28;ctx.drawImage(ghost,0,0);ctx.globalAlpha=1;
    }
    if(layers.outlines)ctx.drawImage(contour,0,0,w,h);
    return {segmentation:available,blur:layers.blur&&'filter' in ctx};
  };
}
function drawSilhouette(ctx,t,w,h){
  const s=t.scale*h,cx=t.centerX*w,sy=t.shoulderY*h;
  ctx.beginPath();ctx.ellipse(cx,sy-.38*s,.23*s,.29*s,0,0,Math.PI*2);ctx.fill();
  ctx.beginPath();if(ctx.roundRect)ctx.roundRect(cx-.14*s,sy-.18*s,.28*s,.3*s,.08*s);else ctx.rect(cx-.14*s,sy-.18*s,.28*s,.3*s);ctx.fill();
  ctx.beginPath();ctx.moveTo(cx-.53*s,sy);ctx.quadraticCurveTo(cx,sy-.15*s,cx+.53*s,sy);
  ctx.lineTo(cx+.31*s,sy+.72*s);ctx.lineTo(cx+.46*s,sy+1.12*s);
  ctx.quadraticCurveTo(cx,sy+1.3*s,cx-.46*s,sy+1.12*s);ctx.lineTo(cx-.31*s,sy+.72*s);ctx.closePath();ctx.fill();
  const capsule=(a,b,r)=>{
    const pa=t.points[a],pb=t.points[b],ax=pa.x*w,ay=pa.y*h,bx=pb.x*w,by=pb.y*h;
    const angle=Math.atan2(by-ay,bx-ax),dx=Math.sin(angle)*r,dy=-Math.cos(angle)*r;
    ctx.beginPath();ctx.moveTo(ax+dx,ay+dy);ctx.lineTo(bx+dx,by+dy);ctx.arc(bx,by,r,angle-Math.PI/2,angle+Math.PI/2);ctx.lineTo(ax-dx,ay-dy);ctx.arc(ax,ay,r,angle+Math.PI/2,angle+3*Math.PI/2);ctx.fill();
  };
  for(const [a,b] of [[11,13],[13,15],[12,14],[14,16]])capsule(a,b,.115*s);
  for(const [a,b] of [[23,25],[25,27],[24,26],[26,28]])capsule(a,b,.16*s);
  for(const i of [27,28]){ctx.beginPath();ctx.ellipse(t.points[i].x*w,t.points[i].y*h,.23*s,.12*s,0,0,Math.PI*2);ctx.fill();}
}
