import test from 'node:test';
import assert from 'node:assert/strict';
import {targetLayout,positionMatch,shortGuidance,groupReady,guideLayers,containRect,screenPoint,maskPixels,usableMasks,createGuideRenderer} from '../src/features/livePose/visualGuide.js';
import {trackGroup} from '../src/features/livePose/groupTracking.js';
const rec=(ids=['relaxed'],spacing='none')=>({spacing,people:ids.map((pose_id,i)=>({person:i+1,pose_id}))});
const landmarks=t=>{const p=Array.from({length:33},()=>({x:t.centerX,y:t.shoulderY,visibility:1}));for(const [i,point] of Object.entries(t.points))p[i]={...point,visibility:1};return p;};
test('silhouettes require a supported AI recommendation and fit the image',()=>{
  assert.deepEqual(targetLayout(null,1),[]);assert.deepEqual(targetLayout(rec(['sitting']),1),[]);
  for(const aspect of [9/16,1,4/3,16/9])for(const ids of [['relaxed'],['hands_hips','relaxed'],['arms_open','left_hip','relaxed']]){
    for(const target of targetLayout(rec(ids),aspect))for(const p of Object.values(target.points)){assert.ok(p.x>0&&p.x<1&&p.y>0&&p.y<1);}
  }
  assert.equal(targetLayout(rec(['arms_open','arms_open','arms_open'],'wide'),9/16).length,0);
});
test('matching posture away from the target cannot turn green; matching the displayed geometry can',()=>{
  const recommendation=rec(),aspect=4/3,targets=targetLayout(recommendation,aspect),person=landmarks(targets[0]);
  let state=null;
  for(let t=0;t<=1900;t+=100)state=trackGroup(state,[person],recommendation,1,t,aspect,targets);
  assert.equal(state.people[0].state,'green');
  const shifted=person.map(p=>({...p,x:p.x+.12}));
  for(let t=2000;t<=3900;t+=100)state=trackGroup(state,[shifted],recommendation,1,t,aspect,targets);
  assert.equal(state.people[0].state,'red');assert.equal(shortGuidance(state.people[0]),'Move Left');
  assert.equal(shortGuidance(state.people[0],true),'Move Right');
});
test('each group silhouette has its own stable measurable location',()=>{
  const recommendation=rec(['relaxed','hands_hips','left_hip'],'comfortable'),aspect=16/9,targets=targetLayout(recommendation,aspect);
  let state=null;for(let t=0;t<=2000;t+=100)state=trackGroup(state,targets.map(landmarks),recommendation,3,t,aspect,targets);
  assert.ok(state.people.every(p=>p.state==='green'));assert.equal(groupReady(state,recommendation),true);
  state.group.state='neutral';assert.equal(groupReady(state,recommendation),false);
});
test('contain alignment handles portrait, landscape, letterboxing and mirroring exactly once',()=>{
  for(const [vw,vh,w,h] of [[1280,720,360,640],[720,1280,640,360],[640,480,360,600]]){
    const rect=containRect(vw,vh,w,h),a=screenPoint({x:.2,y:.6},rect,false),b=screenPoint({x:.2,y:.6},rect,true);
    assert.ok(Math.abs(a.x+b.x-(2*rect.x+rect.width))<1e-8);assert.equal(a.y,b.y);
    assert.ok(Math.abs(rect.width/rect.height-vw/vh)<1e-8);
  }
});
test('position guidance accounts for apparent scale as well as position',()=>{
  const target=targetLayout(rec(),1)[0],g={x:target.hip.x,y:target.hip.y,scale:target.scale};
  assert.equal(positionMatch(g,target,1).matches,true);
  assert.equal(positionMatch({...g,scale:g.scale*.5},target,1).guidance,'Step Closer');
  assert.equal(positionMatch({...g,scale:g.scale*1.5},target,1).guidance,'Step Back');
});
const mask=()=>({width:8,height:8,data:Float32Array.from({length:64},(_,i)=>i%8>=2&&i%8<=5&&Math.floor(i/8)>=2&&Math.floor(i/8)<=5?.9:.1)});
test('contours are real segmentation edges, not skeleton approximations',()=>{
  const {union,edges}=maskPixels([mask()],['green'],8,8);
  assert.equal(union[(3*8+3)*4+3],255);assert.equal(edges[(3*8+3)*4+3],0);
  assert.deepEqual([...edges.slice((2*8+2)*4,(2*8+2)*4+4)],[50,230,152,255]);
  assert.equal(union[3],0);
  assert.deepEqual([...maskPixels([mask()],['neutral'],8,8).edges.slice((2*8+2)*4,(2*8+2)*4+4)],[180,191,208,255]);
});
test('missing, blank or invalid masks disable blur and outlines',()=>{
  const result={count:1,people:[]};assert.equal(usableMasks([mask()],result),true);
  for(const masks of [[],[{...mask(),data:new Float32Array(64)}],[{...mask(),data:new Float32Array(64).fill(NaN)}]])assert.equal(usableMasks(masks,result),false);
  assert.deepEqual(guideLayers(true,true,false),{targets:true,outlines:false,blur:false});
});
test('hiding guidance removes targets, contours and preview blur',()=>{
  assert.deepEqual(guideLayers(false,true,true),{targets:false,outlines:false,blur:false});
  const operations=[];
  const fake=()=>({width:0,height:0,getContext:()=>({clearRect:()=>operations.push('clear'),drawImage:()=>operations.push('draw')})});
  const render=createGuideRenderer(fake(),fake);
  render({width:640,height:480},[mask()],{count:1,people:[]},targetLayout(rec(),4/3),{visible:false,blur:true});
  assert.deepEqual(operations,['clear']);
});
test('segmented blur composites sharp foreground and contours, with no invented fallback',()=>{
  const surfaces=[];
  const make=()=>{
    const events=[],ctx={filter:'none',clearRect(){events.push('clear');},drawImage(){events.push(`draw:${this.filter}:${this.globalCompositeOperation||'source-over'}`);},createImageData(w,h){return {data:new Uint8ClampedArray(w*h*4)};},putImageData(){events.push('pixels');}};
    const canvas={width:0,height:0,getContext:()=>ctx,ctx,events};surfaces.push(canvas);return canvas;
  };
  const canvas=make(),render=createGuideRenderer(canvas,make),frame={width:640,height:480};
  const result={count:1,people:[{detectionIndex:0,state:'red'}]};
  const effects=render(frame,[mask()],result,[],{visible:true,blur:true});
  assert.equal(effects.blur,true);assert.ok(canvas.events.includes('draw:blur(3px):source-over'));
  assert.ok(surfaces.some(c=>c.events.includes('draw:none:destination-in')));
  canvas.events.length=0;
  const fallback=render(frame,[],result,[],{visible:true,blur:true});
  assert.equal(fallback.blur,false);assert.equal(fallback.segmentation,false);
  assert.ok(!canvas.events.some(e=>e.includes('blur(')));
});
