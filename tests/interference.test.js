const test=require('node:test');
const assert=require('node:assert/strict');
const {build}=require('../interference-options');
const DualAudioQuestion=require('../dual-audio');
global.window={};for(const file of ['songs','previews','decoys','ghibli-themes'])require('../'+file);
const {SONGS:songs,SONG_PREVIEWS:previews,DECOYS:decoys,GHIBLI_THEMES:themeOptions}=window;
const titleKey=s=>s.replace(/\s*[（(【\[].*$/,'').replace(/\s+[-–—]\s+.*$/,'').trim().toLowerCase();
let seed=19;
function shuffle(list){const a=list.slice();for(let i=a.length-1;i>0;i--){seed=(seed*1664525+1013904223)>>>0;const j=Math.floor(seed/4294967296*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;}
const config={songs,previews,decoys,themeOptions,shuffle,titleKey};
test('Hisaishi demo has two playable Miyazaki pieces plus seven real film themes',()=>{
  const titles=new Set(themeOptions.map(s=>titleKey(s.title)));
  for(const answer of songs.filter(s=>s.artist==='久石讓')){
    for(let n=0;n<20;n++){
      const {options,interferenceSong}=build(answer,config);
      assert.equal(options.length,9);assert.equal(new Set(options.map(s=>titleKey(s.title))).size,9);
      assert(options.includes(answer)&&options.includes(interferenceSong));
      assert.notEqual(answer.id,interferenceSong.id);assert.equal(interferenceSong.artist,'久石讓');
      assert.equal(options.filter(s=>s.themeOption).length,7);
      assert(options.every(s=>titles.has(titleKey(s.title)) && !s.invented));
      assert.equal(new Set(options.map(s=>themeOptions.find(t=>t.title===s.title).workKey)).size,9);
    }
  }
});
test('ordinary questions include a different playable real option, with unique titles',()=>{
  for(const answer of songs.filter(s=>s.artist!=='久石讓')){
    const {options,interferenceSong}=build(answer,config);
    assert.equal(options.length,9);assert.equal(new Set(options.map(s=>titleKey(s.title))).size,9);
    assert(options.includes(answer)&&options.includes(interferenceSong));
    assert(previews[interferenceSong.id].url);assert.notEqual(answer.id,interferenceSong.id);
    assert(options.every(s=>!s.invented));
  }
});
function media(){return {readyState:4,currentTime:0,paused:true,volume:1,plays:0,play(){this.plays++;this.paused=false;return Promise.resolve();},pause(){this.paused=true;}};}
test('interference waits for 2.5 seconds of actual playback; applies relative volume',async()=>{
  const primary=media(),interference=media();
  const clip=new DualAudioQuestion({primary,interference,primaryOffset:5,volume:.8});
  try{
    await clip.start();assert.equal(primary.volume,.8);assert(Math.abs(interference.volume-.4)<1e-9);
    primary.currentTime=7.49;clip.checkProgress();assert.equal(interference.plays,0);
    primary.paused=true;primary.currentTime=7.5;clip.checkProgress();assert.equal(interference.plays,0);
    primary.paused=false;clip.checkProgress();await Promise.resolve();assert.equal(interference.plays,1);
    clip.checkProgress();assert.equal(interference.plays,1);
    clip.setVolume(.4);assert.equal(primary.volume,.4);assert(Math.abs(interference.volume-.2)<1e-9);
  }finally{clip.stop();}
  assert(primary.paused&&interference.paused);
});
test('answer before 2.5 seconds cancels pending interference',async()=>{
  const primary=media(),interference=media(),clip=new DualAudioQuestion({primary,interference});
  await clip.start();clip.stop();primary.currentTime=3;clip.checkProgress();assert.equal(interference.plays,0);
});
test('late playback promise cannot restart audio after answer',async()=>{
  const primary=media(),interference=media();let finish;
  interference.play=function(){this.plays++;return new Promise(resolve=>{finish=()=>{this.paused=false;resolve();};});};
  const clip=new DualAudioQuestion({primary,interference});
  await clip.start();primary.currentTime=2.5;clip.checkProgress();clip.stop();finish();
  await new Promise(resolve=>setImmediate(resolve));assert(interference.paused);
});
test('ready audio starts within the retry click without an asynchronous readiness wait',async()=>{
  const primary=media(),interference=media();
  const clip=new DualAudioQuestion({primary,interference});
  const start=clip.start();
  assert.equal(primary.plays,1,'play() must be called before returning to the event loop');
  await start;clip.stop();
});
test('autoplay permission errors retain their name for the retry UI',async()=>{
  const primary=media(),interference=media();
  primary.play=()=>Promise.reject(Object.assign(new Error('Blocked'),{name:'NotAllowedError'}));
  const clip=new DualAudioQuestion({primary,interference});
  await assert.rejects(clip.start(),{name:'NotAllowedError'});
  clip.stop();assert(primary.paused && interference.paused);
});
