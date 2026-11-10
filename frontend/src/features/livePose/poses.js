// Coordinates in torso lengths, origin at shoulder midpoint. Anatomical left is +x.
const base = {11:[.5,0],12:[-.5,0],23:[.35,1],24:[-.35,1],25:[.35,1.9],26:[-.35,1.9],27:[.35,2.8],28:[-.35,2.8]};
const downLeft = {13:[.58,.65],15:[.58,1.3]};
const downRight = {14:[-.58,.65],16:[-.58,1.3]};
const hipLeft = {13:[1,.55],15:[.4,1]};
const hipRight = {14:[-1,.55],16:[-.4,1]};
export const POSES = [
  {id:'relaxed',name:'Relaxed standing',instruction:'Face the camera, stand tall and let both arms hang by your sides.',points:{...base,...downLeft,...downRight}},
  {id:'hands_hips',name:'Hands on hips',instruction:'Face the camera. Place both hands on your hips, with elbows outward.',points:{...base,...hipLeft,...hipRight}},
  {id:'left_hip',name:'Left hand on hip',instruction:'Put your left hand on your hip. Keep your right arm down.',points:{...base,...hipLeft,...downRight}},
  {id:'right_hip',name:'Right hand on hip',instruction:'Put your right hand on your hip. Keep your left arm down.',points:{...base,...downLeft,...hipRight}},
  {id:'arms_open',name:'Open arms',instruction:'Extend both arms sideways at shoulder height. Stand tall with feet under your hips.',points:{...base,13:[1.15,0],15:[1.8,0],14:[-1.15,0],16:[-1.8,0]}},
];
export const EDGES = [[11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24],[23,24],[23,25],[25,27],[24,26],[26,28]];
const IDS = Object.keys(base).map(Number).concat([13,14,15,16]);
export function evaluatePose(landmarks, pose, aspect=1) {
  const neutral = (guidance) => ({state:'neutral',matches:false,guidance});
  if (!landmarks?.length || !pose?.points) return neutral('Step back until your full body is visible.');
  if (IDS.some(i => !landmarks[i] || (!Number.isFinite(landmarks[i].visibility) || landmarks[i].visibility<.65) || !Number.isFinite(landmarks[i].x) || !Number.isFinite(landmarks[i].y) || landmarks[i].x<0 || landmarks[i].x>1 || landmarks[i].y<0 || landmarks[i].y>1)) return neutral('Keep your shoulders, hands and feet visible in good light.');
  const p=landmarks.map(p=>({x:p.x*aspect,y:p.y}));
  const origin={x:(p[11].x+p[12].x)/2,y:(p[11].y+p[12].y)/2};
  const hip={x:(p[23].x+p[24].x)/2,y:(p[23].y+p[24].y)/2};
  const scale=Math.hypot(hip.x-origin.x,hip.y-origin.y);
  if(scale<.08 || Math.abs(p[11].x-p[12].x)/scale<.45) return neutral('Face the camera with your full body in view.');
  const sign=Math.sign(p[11].x-p[12].x);
  const normalized=Object.fromEntries(IDS.map(i=>[i,[(p[i].x-origin.x)*sign/scale,(p[i].y-origin.y)/scale]]));
  const errors=IDS.map(i=>({i,d:Math.hypot(normalized[i][0]-pose.points[i][0],normalized[i][1]-pose.points[i][1])}));
  const worst=errors.sort((a,b)=>b.d-a.d)[0];
  // Every measured joint must agree; an average cannot hide a badly positioned arm.
  const matches=worst.d<.42;
  let guidance='Hold this position steadily.';
  if (!matches) {
    const side=[13,15].includes(worst.i)?'left':'right';
    if([13,14,15,16].includes(worst.i)) {
      const hipPose=pose.id==='hands_hips'||pose.id===`${side}_hip`;
      guidance=pose.id==='arms_open'?`Extend your ${side} arm sideways at shoulder height.`:hipPose?`Place your ${side} hand on your hip, elbow outward.`:`Lower your ${side} arm beside your body.`;
    } else guidance='Stand upright, facing the camera, with feet under your hips.';
  }
  return {state:'red', matches, guidance};
}
export function stability(previous, result, now) {
  if(!result.matches) return {since:null,last:now,state:result.state};
  const since=previous?.since!=null && now-previous.last<400 ? previous.since : now;
  return {since,last:now,state:now-since>=900?'green':'red'};
}
