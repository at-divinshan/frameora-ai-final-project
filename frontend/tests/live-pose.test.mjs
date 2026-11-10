import test from 'node:test';
import assert from 'node:assert/strict';
import {POSES,evaluatePose,stability} from '../src/features/livePose/poses.js';
function landmarks(pose,{scale=.2,x=.5,y=.18,aspect=1,mirror=false}={}){
  const points=Array.from({length:33},()=>({x:.5,y:.5,visibility:1}));
  for(const [i,[px,py]] of Object.entries(pose.points))points[i]={x:(x+(mirror?-1:1)*px*scale)/aspect,y:y+py*scale,visibility:1};
  return points;
}
test('all supported templates match real normalized coordinates across scale, aspect and mirror',()=>{
  for(const pose of POSES)for(const opts of [{},{scale:.15,x:.4},{aspect:1.5},{mirror:true}])assert.equal(evaluatePose(landmarks(pose,opts),pose,opts.aspect||1).matches,true,pose.id);
});
test('different arm poses do not accidentally match',()=>{
  for(const target of POSES)for(const actual of POSES)if(target.id!==actual.id)assert.equal(evaluatePose(landmarks(actual),target).matches,false,`${actual.id} vs ${target.id}`);
});
test('missing, occluded, invalid and out-of-frame body points are neutral',()=>{
  assert.equal(evaluatePose([],POSES[0]).state,'neutral');
  for(const bad of [{visibility:.1},{x:2},{x:NaN}]){
    const points=landmarks(POSES[0]);Object.assign(points[15],bad);assert.equal(evaluatePose(points,POSES[0]).state,'neutral');
  }
});
test('green requires a stable interval and resets on tracking loss or frame gap',()=>{
  let state=null;for(let t=0;t<=800;t+=100){state=stability(state,{matches:true},t);assert.equal(state.state,'red');}
  state=stability(state,{matches:true},900);assert.equal(state.state,'green');
  state=stability(state,{matches:false,state:'neutral'},1000);assert.equal(state.state,'neutral');
  state=stability(state,{matches:true},1100);assert.equal(state.state,'red');
  state=stability(state,{matches:true},2100);assert.equal(state.state,'red');
});
test('guidance names the anatomical arm that differs',()=>{
  const result=evaluatePose(landmarks(POSES[0]),POSES.find(p=>p.id==='left_hip'));
  assert.match(result.guidance,/left hand on your hip/);
});

const {trackGroup,supportedAnalysis}=await import('../src/features/livePose/groupTracking.js');
const recommendation=(ids=['relaxed'],spacing='none')=>({instructions:'Stand facing camera.',people:ids.map((pose_id,i)=>({person:i+1,pose_id,instructions:'Follow the target.'})),spacing});
const bodies=(ids=['relaxed'],positions=[.5])=>ids.map((id,i)=>landmarks(POSES.find(p=>p.id===id),{scale:.16,x:positions[i],y:.15}));
function held(detections,rec,steps=18){let state=null;for(let i=0;i<=steps;i++)state=trackGroup(state,detections,rec,rec.people.length,i*100);return state;}
test('solo automatically uses assigned target and reaches stable green',()=>{
  const result=held(bodies(),recommendation());assert.equal(result.people[0].state,'green');
});
test('two and three people are scored independently, not averaged',()=>{
  const result=held(bodies(['relaxed','relaxed'],[.25,.75]),recommendation(['relaxed','arms_open']));
  assert.equal(result.people[0].state,'green');assert.equal(result.people[1].state,'red');
  const three=held(bodies(['relaxed','hands_hips','left_hip'],[.2,.5,.8]),recommendation(['relaxed','hands_hips','left_hip']));
  assert.deepEqual(three.people.map(p=>p.state),['green','green','green']);
});
test('detector array reordering preserves geometric association and hold timers',()=>{
  const detections=bodies(['relaxed','hands_hips'],[.25,.75]),rec=recommendation(['relaxed','hands_hips']);
  let state=held(detections,rec);state=trackGroup(state,[...detections].reverse(),rec,2,1900);
  assert.deepEqual(state.people.map(p=>p.state),['green','green']);
  assert.equal(state.people[0].points,detections[0]);
});
test('no person, count mismatch, unsupported templates and absent AI remain neutral',()=>{
  assert.equal(trackGroup(null,[],recommendation(),1,0).group.state,'neutral');
  for(const [rec,count] of [[null,0],[recommendation(['dance']),1],[recommendation(['relaxed','relaxed']),2]]){
    const result=trackGroup(null,bodies(),rec,count,0);assert.equal(result.people[0].state,'neutral');
  }
});
test('occluded or out-of-frame joints are neutral while other reliable bodies keep matching',()=>{
  const detections=bodies(['relaxed','relaxed'],[.25,.75]),rec=recommendation(['relaxed','relaxed'],'comfortable');
  let state=held(detections,rec);detections[1][15].visibility=.1;
  state=trackGroup(state,detections,rec,2,1900);
  assert.equal(state.people[0].state,'green');assert.equal(state.people[1].state,'neutral');assert.equal(state.group.state,'neutral');
  detections[1][15].visibility=1;detections[1][27].y=1.2;
  state=trackGroup(state,detections,rec,2,2000);assert.equal(state.people[1].state,'neutral');
});
test('overlap, a long frame gap, disappearance and fast movement never inherit green',()=>{
  const rec=recommendation(['relaxed','relaxed']),detections=bodies(['relaxed','relaxed'],[.25,.75]);
  const previous=held(detections,rec);
  for(const [next,now] of [[bodies(['relaxed','relaxed'],[.46,.54]),1900],[detections,2700],[detections.slice(0,1),1900],[bodies(['relaxed','relaxed'],[.44,.85]),1900]]){
    const result=trackGroup(previous,next,rec,2,now);assert.ok(result.people.every(p=>p.state==='neutral'));
  }
});
test('relative spacing uses torso-normalized geometry and stable holds',()=>{
  const rec=recommendation(['relaxed','relaxed'],'close');
  const far=held(bodies(['relaxed','relaxed'],[.2,.8]),rec);assert.equal(far.group.state,'red');assert.match(far.group.guidance,/closer/);
  const matched=held(bodies(['relaxed','relaxed'],[.35,.65]),rec);assert.equal(matched.group.state,'green');
  const near=held(bodies(['relaxed','relaxed'],[.4,.6]),recommendation(['relaxed','relaxed'],'wide'));
  assert.equal(near.group.state,'red');assert.match(near.group.guidance,/more space/);
});
test('different apparent depths prevent precise group matching',()=>{
  const detections=[landmarks(POSES[0],{scale:.12,x:.25}),landmarks(POSES[0],{scale:.2,x:.75})];
  const result=held(detections,recommendation(['relaxed','relaxed'],'comfortable'));
  assert.equal(result.group.state,'neutral');assert.match(result.group.guidance,/perspective/);
});
test('malformed, legacy and unsupported AI suggestions are never treated as trackable',()=>{
  const valid={detected_people_count:1,suggestions:[recommendation(),recommendation(['hands_hips']),recommendation(['left_hip'])]};
  assert.equal(supportedAnalysis(valid),true);
  for(const data of [{poses:[]},{...valid,detected_people_count:0},{...valid,detected_people_count:4},{...valid,suggestions:[recommendation(['sitting'])]}])assert.equal(supportedAnalysis(data),false);
});
test('an extra fourth detection disables scoring instead of matching a subset',()=>{
  const rec=recommendation(['relaxed','relaxed','relaxed']);
  const result=trackGroup(null,bodies(['relaxed','relaxed','relaxed','relaxed'],[.15,.38,.62,.85]),rec,3,1000);
  assert.equal(result.count,4);assert.equal(result.people.length,4);
  assert.ok(result.people.every(p=>p.state==='neutral'));
});
