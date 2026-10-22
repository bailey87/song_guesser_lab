/* Two media elements, scheduled against actual primary playback progress. */
(function(root){
  function waitForData(el, timeout=10000){
    if(el.readyState>=2) return Promise.resolve();
    return new Promise((resolve,reject)=>{
      const done=error=>{
        clearTimeout(timer);
        el.removeEventListener('loadeddata',ok);el.removeEventListener('canplay',ok);el.removeEventListener('error',bad);
        error?reject(error):resolve();
      };
      const ok=()=>done(),bad=()=>done(new Error('音源無法載入'));
      const timer=setTimeout(()=>done(new Error('音源載入逾時')),timeout);
      el.addEventListener('loadeddata',ok);el.addEventListener('canplay',ok);el.addEventListener('error',bad);
    });
  }
  async function playWithTimeout(el){
    let timer;
    try{await Promise.race([el.play(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('播放逾時')),10000);})]);}
    finally{clearTimeout(timer);}
  }
  class DualAudioQuestion {
    constructor({primary,interference,primaryOffset=0,interferenceOffset=0,volume=.8,delay=2,ratio=.7,onInterference=()=>{},onError=()=>{}}){
      Object.assign(this,{primary,interference,primaryOffset,interferenceOffset,delay,ratio,onInterference,onError});
      this.stopped=false;this.triggered=false;this.timer=null;
      this.setVolume(volume);
    }
    setVolume(value){
      this.volume=Math.min(1,Math.max(0,value));
      this.primary.volume=this.volume;this.interference.volume=this.volume*this.ratio;
    }
    async start(){
      await Promise.all([waitForData(this.primary),waitForData(this.interference)]);
      if(this.stopped) return;
      this.primary.currentTime=this.primaryOffset;
      this.interference.currentTime=this.interferenceOffset;
      await playWithTimeout(this.primary);
      if(this.stopped){this.primary.pause();return;}
      this.timer=setInterval(()=>this.checkProgress(),25);
    }
    checkProgress(){
      if(this.stopped||this.triggered||this.primary.paused) return;
      const elapsed=this.primary.currentTime-this.primaryOffset;
      if(elapsed<this.delay) return;
      this.triggered=true;
      clearInterval(this.timer);this.timer=null;
      this.startedAtPrimarySeconds=elapsed;
      playWithTimeout(this.interference).then(()=>{
        if(this.stopped){this.interference.pause();return;}
        this.onInterference();
      }).catch(error=>{if(!this.stopped) this.onError(error);});
    }
    stop(){
      this.stopped=true;clearInterval(this.timer);this.timer=null;
      this.primary.pause();this.interference.pause();
    }
  }
  root.DualAudioQuestion=DualAudioQuestion;
  if(typeof module!=='undefined'&&module.exports) module.exports=DualAudioQuestion;
})(typeof window==='undefined'?globalThis:window);
