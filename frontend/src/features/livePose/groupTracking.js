import { POSES, evaluatePose, stability } from './poses.js';
import { positionMatch } from './visualGuide.js';
export const MAX_PEOPLE = 3;
// One extra detection is an overflow guard, never a scored fourth person.
export const DETECTION_LIMIT = MAX_PEOPLE + 1;
const poseMap = Object.fromEntries(POSES.map(p => [p.id,p]));
export function supportedAnalysis(data) {
  const count=data?.detected_people_count;
  return Number.isInteger(count) && count>0 && count<=MAX_PEOPLE && Array.isArray(data.suggestions) && data.suggestions.length>=3 && data.suggestions.length<=5 && data.suggestions.every(s=>
    typeof s.instructions==='string' && ['none','close','comfortable','wide'].includes(s.spacing) &&
    (count!==1||s.spacing==='none') && Array.isArray(s.people) && s.people.length===count &&
    new Set(s.people.map(p=>p.person)).size===count && s.people.every(p=>Number.isInteger(p.person)&&p.person>=1&&p.person<=count&&poseMap[p.pose_id]&&typeof p.instructions==='string'));
}
function geometry(points, aspect) {
  if([11,12,23,24].some(i=>!points[i] || (!Number.isFinite(points[i].visibility)||points[i].visibility<.65) || !Number.isFinite(points[i].x)||!Number.isFinite(points[i].y)||points[i].x<0||points[i].x>1||points[i].y<0||points[i].y>1))return null;
  const x=(points[23].x+points[24].x)/2*aspect, y=(points[23].y+points[24].y)/2;
  const scale=Math.hypot(x-(points[11].x+points[12].x)/2*aspect,y-(points[11].y+points[12].y)/2);
  return scale>.06?{x,y,scale}:null;
}
function permutations(items) {
  if(items.length<2)return [items];
  return items.flatMap((item,i)=>permutations(items.filter((_,j)=>i!==j)).map(rest=>[item,...rest]));
}
const neutral=guidance=>({state:'neutral',matches:false,guidance});

// These are temporary geometric associations, never identity recognition. Slots are
// assigned left-to-right in unmirrored video. Crossings, gaps and ambiguous matches
// reset ALL hold timers instead of transferring a green state to another body.
export function trackGroup(previous, detections, recommendation, expectedCount, now, aspect=1, targets=null) {
  const bodies=detections.slice(0,DETECTION_LIMIT).map((points,detectionIndex)=>({points,detectionIndex,geometry:geometry(points,aspect)}));
  const result={last:now,tracks:[],people:[],count:detections.length,group:neutral('Analyze the scene to get measurable targets.')};
  const unmapped=(guidance)=>{
    result.people=bodies.map(b=>({...b,...neutral(guidance),person:null}));
    result.group=neutral(guidance);return result;
  };
  if(!recommendation)return unmapped(detections.length?'Analyze the scene for automatic pose recommendations.':'No people detected. Step into the frame.');
  if(!expectedCount||expectedCount>MAX_PEOPLE||!Array.isArray(recommendation.people)||recommendation.people.length!==expectedCount||new Set(recommendation.people.map(p=>p.person)).size!==expectedCount||recommendation.people.some(p=>!poseMap[p.pose_id]||!Number.isInteger(p.person)||p.person<1||p.person>expectedCount))return unmapped('This recommendation has no supported measurable targets. Reanalyze the scene.');
  if(targets&&targets.length!==expectedCount)return unmapped('Turn Phone Sideways');
  if(detections.length!==expectedCount)return unmapped(`Seeing ${detections.length} of ${expectedCount} expected people. Keep everyone visible or reanalyze if the group changed.`);
  if(bodies.some(b=>!b.geometry))return unmapped('Person association is uncertain. Keep everyone’s shoulders and hips visible.');
  const ordered=[...bodies].sort((a,b)=>a.geometry.x-b.geometry.x);
  const crowded=ordered.some((b,i)=>i && (b.geometry.x-ordered[i-1].geometry.x)/Math.max(b.geometry.scale,ordered[i-1].geometry.scale)<.65);
  if(crowded)return unmapped('Bodies overlap. Separate slightly so each person can be tracked.');
  const old=previous?.tracks || [];
  let assigned=ordered, reuse=old.length===expectedCount && now-previous.last<400;
  if(reuse){
    const choices=permutations(bodies).map(order=>({order,cost:order.reduce((sum,b,i)=>sum+Math.hypot(b.geometry.x-old[i].geometry.x,b.geometry.y-old[i].geometry.y)/old[i].geometry.scale,0)})).sort((a,b)=>a.cost-b.cost);
    const best=choices[0];
    const uncertain=(choices[1]&&choices[1].cost-best.cost<.35)||best.order.some((b,i)=>Math.hypot(b.geometry.x-old[i].geometry.x,b.geometry.y-old[i].geometry.y)/old[i].geometry.scale>.9)||best.order.some((b,i)=>i&&b.geometry.x<best.order[i-1].geometry.x);
    if(uncertain)return unmapped('People moved or crossed. Hold still while the guide reassociates positions.');
    assigned=best.order;
  }
  result.tracks=assigned.map((b,i)=>{
    const target=recommendation.people.find(p=>p.person===i+1);
    const acquired=reuse?old[i].acquired:now;
    let measured=evaluatePose(b.points,poseMap[target.pose_id],aspect);
    if(targets && measured.state!=='neutral'){
      const position=positionMatch(b.geometry,targets.find(t=>t.person===i+1),aspect);
      if(!position.matches)measured={state:'red',...position};
    }
    if(now-acquired<600)measured=neutral('Hold position while your body is associated.');
    const hold=stability(reuse?old[i].hold:null,measured,now);
    return {...b,person:i+1,acquired,hold,state:hold.state,guidance:hold.state==='green'?'Posture matched — hold steady.':measured.guidance};
  });
  result.people=result.tracks;
  if(result.people.some(p=>p.state==='neutral'))result.group=neutral('Group matching needs reliable full-body visibility for everyone.');
  else if(expectedCount===1||recommendation.spacing==='none')result.group=neutral('Only individual posture is measured; group composition is not scored.');
  else {
    const scales=result.tracks.map(t=>t.geometry.scale);
    const hips=result.tracks.map(t=>t.geometry.y);
    const mean=scales.reduce((a,b)=>a+b,0)/scales.length;
    if(Math.max(...scales)/Math.min(...scales)>1.35||(Math.max(...hips)-Math.min(...hips))/mean>.5)result.group=neutral('Depth or perspective differs. Group spacing cannot be matched reliably.');
    else {
      const range={close:[1.2,2.2],comfortable:[1.8,3.2],wide:[3,5]}[recommendation.spacing];
      if(!range)result.group=neutral('Group spacing target is unsupported.');
      else {
        const gaps=result.tracks.slice(1).map((t,i)=>(t.geometry.x-result.tracks[i].geometry.x)/((t.geometry.scale+result.tracks[i].geometry.scale)/2));
        const far=gaps.some(g=>g>range[1]),near=gaps.some(g=>g<range[0]);
        const match=!far&&!near;
        const hold=stability(reuse?previous.group?.hold:null,{matches:match,state:'red'},now);
        result.group={state:hold.state,hold,guidance:far?'Move a little closer together.':near?'Leave a little more space between you.':hold.state==='green'?'Approximate spacing matched.':'Hold this spacing steadily.'};
      }
    }
  }
  return result;
}
