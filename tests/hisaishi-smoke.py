"""Exercise each Hisaishi question with real audio and all eight invented labels.
Uses a controlled single-question pool to inspect all 20, not normal random play.
Requires Python Playwright, Chromium and a valid HTTPS trust configuration.
"""
import functools
import http.server
import json
import os
from pathlib import Path
import shutil
import threading
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
results=[]
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':390,'height':844})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='domcontentloaded')
        assert '710' in page.locator('#library-info').inner_text()
        page.locator('#nick').fill('MusicTest');page.locator('#btn-test').click()
        page.evaluate('''() => {
            CONFIG.revealMs=10;
            R.questionCount=20;
            window.hisaishiQuestions=buildQuestions(SONGS.filter(s=>s.artist==='久石讓'),{});
            R.questionCount=1;
            G.nickname='MusicTest';
        }''')
        for i in range(20):
            page.evaluate('''i => {
                G.questions=[hisaishiQuestions[i]];G.index=0;G.total=0;G.log=[];
                show('screen-play');nextQuestion();
            }''',i)
            page.wait_for_function('!G.locked && G.questions[0].audio?.source==="preview"',timeout=30000)
            page.wait_for_function('G.questions[0].audio.el.currentTime>0 && !G.questions[0].audio.el.paused',timeout=10000)
            observed=page.evaluate('''() => {
                const q=G.questions[0];
                return {id:q.song.id,title:q.song.title,
                    options:Array.from(document.querySelectorAll('#grid button'),b=>b.textContent),
                    expected:[q.song.title,...NAMED_DECOYS[q.song.id]],
                    invented:q.options.filter(o=>o.invented).length,
                    answerIndex:q.options.indexOf(q.song),
                    audioSource:q.audio.source,playbackSeconds:q.audio.el.currentTime};
            }''')
            assert len(observed['options'])==9 and len(set(observed['options']))==9
            assert set(observed.pop('expected'))==set(observed['options'])
            assert observed['invented']==8
            if i==0:page.screenshot(path='/tmp/hisaishi-grid.png')
            page.locator('#grid button').nth(observed.pop('answerIndex')).click()
            page.wait_for_function('G.index===1 && !document.querySelector("#screen-result").hidden')
            assert page.evaluate('G.log[0].correct')
            results.append(observed)
            print('PASS',observed['title'],': nine distinct labels, correct answer, real playback',flush=True)
        assert not errors,errors
        assert len({r['id'] for r in results})==20
        # Normal pop questions keep their original real-title choices.
        assert page.evaluate('''() => {
            R.questionCount=10;
            const qs=buildQuestions(SONGS.filter(s=>s.artist!=='久石讓'),CONFIG.floor);
            return qs.length===10 && qs.every(q=>q.options.length===9 && !q.options.some(o=>o.invented));
        }''')
        browser.close()
    Path('/tmp/hisaishi-browser-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print('PASS: 20/20 audio and invented-option questions; ordinary questions unchanged',flush=True)
finally:
    server.shutdown();server.server_close()
