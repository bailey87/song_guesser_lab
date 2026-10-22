"""Real-audio browser checks for the standalone interference demo."""
import functools,http.server,json,os,shutil,threading
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}'
observations=[]
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':390,'height':844});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url+'/demo.html',wait_until='domcontentloaded')
        page.locator('a[href*="pool=hisaishi"]').click()
        page.wait_for_load_state('domcontentloaded')
        assert page.evaluate('DEMO.enabled && DEMO.hisaishi')
        page.locator('#nick').fill('DemoTest');page.locator('#btn-test').click()
        page.evaluate('CONFIG.revealMs=100')
        page.locator('#btn-speed').click()
        page.wait_for_function('!G.locked && G.clip instanceof DualAudioQuestion',timeout=40000)
        pair=page.evaluate('''() => {
            const q=G.questions[0];window.checkedPair=q;
            return {original:q.song.title,interference:q.interference.song.title,
              realCount:q.options.filter(o=>!o.invented).length,
              fakeCounts:[q.options.filter(o=>o.basedOn===q.song.id).length,q.options.filter(o=>o.basedOn===q.interference.song.id).length]};
        }''')
        assert pair['realCount']==2 and sorted(pair['fakeCounts'])==[3,4]
        page.wait_for_function('G.clip.triggered && G.questions[0].interference.audio.el.currentTime>0',timeout=12000)
        timing=page.evaluate('({start:G.clip.startedAtPrimarySeconds,primary:G.clip.primary.volume,secondary:G.clip.interference.volume,primaryPlaying:!G.clip.primary.paused,secondaryPlaying:!G.clip.interference.paused})')
        assert 2<=timing['start']<=2.3,timing
        assert timing['primaryPlaying'] and timing['secondaryPlaying']
        assert abs(timing['secondary']/timing['primary']-.7)<1e-8
        page.evaluate('setVolume(.4)')
        assert page.evaluate('Math.abs(G.clip.interference.volume-.28)<1e-8 && G.clip.primary.volume===.4')
        page.screenshot(path='/tmp/interference-demo-playing.png')
        observations.append({**pair,**timing})
        # Deliberately select the actual interfering song: it must be wrong.
        page.evaluate("document.querySelectorAll('#grid button')[G.questions[0].options.indexOf(G.questions[0].interference.song)].click()")
        assert page.evaluate('G.log.length===1 && !G.log[0].correct && G.total===0')
        assert page.evaluate('checkedPair.audio.el.paused && checkedPair.interference.audio.el.paused')
        print('PASS real dual playback at 2 seconds, 70% volume and wrong interference answer',flush=True)
        # Complete the remaining nine questions, waiting for both real streams.
        page.evaluate('''() => {
            window.demoObserved=[];
            window.demoAuto=setInterval(()=>{
                if(G.index>=10){clearInterval(demoAuto);return;}
                if(G.locked || !G.clip?.triggered || !(G.clip.interference.currentTime>0))return;
                demoObserved.push({index:G.index,at:G.clip.startedAtPrimarySeconds,original:G.questions[G.index].song.title,interference:G.questions[G.index].interference.song.title});
                document.querySelectorAll('#grid button')[G.questions[G.index].options.indexOf(G.questions[G.index].song)].click();
            },50);
        }''')
        page.wait_for_function('G.index===10 && !document.querySelector("#screen-result").hidden',timeout=180000)
        assert page.evaluate('G.log.filter(x=>x.correct).length')==9
        observations.extend(page.evaluate('demoObserved'))
        assert all(2<=x['at']<=2.3 for x in observations[1:])
        print('PASS complete 10-question Hisaishi interference round',flush=True)
        page.locator('#btn-home').click();page.evaluate('CONFIG.questionCount=1')
        # Real 12-second expiry must stop both players.
        page.locator('#btn-speed').click()
        page.wait_for_function('!G.locked && G.clip instanceof DualAudioQuestion',timeout=40000)
        page.evaluate('window.timeoutPair=G.questions[0]')
        page.wait_for_function('G.index===1 && !document.querySelector("#screen-result").hidden',timeout=20000)
        assert page.evaluate('timeoutPair.audio.el.paused && timeoutPair.interference.audio.el.paused && !G.log[0].correct')
        print('PASS 12-second timeout stops both streams',flush=True)
        page.locator('#btn-home').click();page.locator('#btn-speed').click()
        page.wait_for_function('!G.locked && G.clip instanceof DualAudioQuestion',timeout=40000)
        page.evaluate('''() => {
            window.earlyClip=G.clip;
            document.querySelectorAll('#grid button')[G.questions[0].options.indexOf(G.questions[0].song)].click();
        }''')
        page.wait_for_timeout(2400)
        assert page.evaluate('earlyClip.stopped && !earlyClip.triggered && earlyClip.primary.paused && earlyClip.interference.paused')
        print('PASS early answer cancels delayed interference',flush=True)
        # Simulate a failed secondary load, then exercise the real retry button.
        page.evaluate('''() => {
            R.questionCount=1;G.questions=buildQuestions(stagePool(),{});G.index=0;G.total=0;G.log=[];
            G.questions[0].interference.audio=null;show('screen-play');nextQuestion();
        }''')
        page.locator('#btn-audio-retry').wait_for(state='visible',timeout=40000)
        assert page.evaluate('G.locked && G.log.length===0')
        page.locator('#btn-audio-retry').click()
        page.wait_for_function('!G.locked && G.clip instanceof DualAudioQuestion',timeout=40000)
        page.evaluate("document.querySelectorAll('#grid button')[G.questions[0].options.indexOf(G.questions[0].song)].click()")
        print('PASS failed secondary load locks question and real retry recovers',flush=True)
        # All-language demo includes a real, playable wrong option.
        page.goto(url+'/index.html?interference=1',wait_until='domcontentloaded')
        result=page.evaluate('''() => buildQuestions(SONGS,CONFIG.floor).every(q=>q.options.includes(q.interference.song) && q.song!==q.interference.song && SONG_PREVIEWS[q.interference.song.id]?.url)''')
        assert result
        page.locator('#nick').fill('DemoTest');page.locator('#btn-test').click()
        page.evaluate('''() => {
            R.questionCount=1;
            G.questions=buildQuestions(SONGS.filter(s=>s.artist!=='久石讓'),{});
            G.index=0;G.log=[];G.total=0;show('screen-play');nextQuestion();
        }''')
        page.wait_for_function('!G.locked && G.clip?.triggered && G.clip.interference.currentTime>0',timeout=40000)
        assert page.evaluate('G.questions[0].song.artist!=="久石讓" && !G.clip.primary.paused && !G.clip.interference.paused')
        page.evaluate("document.querySelectorAll('#grid button')[G.questions[0].options.indexOf(G.questions[0].song)].click()")
        print('PASS ordinary-song real dual playback',flush=True)
        # Standard game stays single-track with eight invented Hisaishi labels.
        page.goto(url+'/index.html',wait_until='domcontentloaded')
        assert page.evaluate('!DEMO.enabled && buildQuestions(SONGS,CONFIG.floor).every(q=>!q.interference)')
        assert not errors,errors
        browser.close()
    Path('/tmp/interference-demo-results.json').write_text(json.dumps(observations,ensure_ascii=False,indent=2)+'\n')
    print('PASS demo and standard-game separation; no JavaScript errors',flush=True)
finally:
    server.shutdown();server.server_close()
