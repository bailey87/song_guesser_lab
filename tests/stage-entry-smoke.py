"""Offline Chromium regression: stage entry and autoplay recovery.
Uses a generated local tone, NOT Apple previews or a test of song recognition.
"""
import functools
import http.server
import io
import math
import os
from pathlib import Path
import shutil
import struct
import threading
import wave
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

stream = io.BytesIO()
with wave.open(stream, 'wb') as wav:
    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(8000)
    wav.writeframes(b''.join(struct.pack('<h', int(100 * math.sin(2 * math.pi * 220 * i / 8000))) for i in range(8000 * 30)))
tone = stream.getvalue()
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_port}'
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'), args=['--no-sandbox'])
        for suffix in ['?interference=1', '?interference=1&pool=hisaishi', '']:
            page = browser.new_page(viewport={'width':390, 'height':844})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            # External fonts are irrelevant; all audio under test is synthetic.
            page.route('https://**', lambda route: route.abort())
            page.route('**/test-tone.wav*', lambda route: route.fulfill(body=tone, content_type='audio/wav'))
            page.goto(base + '/index.html' + suffix, wait_until='domcontentloaded')
            page.evaluate('''() => {
                hasLocalAudio=false; CONFIG.revealMs=1;
                for(const preview of Object.values(SONG_PREVIEWS)){
                    preview.url='/test-tone.wav';preview.offset=0;
                }
            }''')
            assert page.locator('#btn-stage').is_disabled()
            page.locator('#nick').fill('StageTest')
            page.locator('#btn-test').click()
            assert page.locator('#btn-stage').is_enabled()
            if suffix:
                # Model a browser requiring a fresh gesture for media playback.
                # This must exercise the real UI retry, not call nextQuestion().
                page.evaluate('''() => {
                    window.nativePlay=HTMLMediaElement.prototype.play;
                    window.requireGesture=true;window.denyOnce=true;
                    HTMLMediaElement.prototype.play=function(){
                        if(denyOnce){
                            denyOnce=false;
                            return Promise.reject(new DOMException('Test initial autoplay denial','NotAllowedError'));
                        }
                        if(requireGesture){
                            if(!navigator.userActivation.isActive)
                                return Promise.reject(new DOMException('Test autoplay policy','NotAllowedError'));
                            requireGesture=false;
                        }
                        return nativePlay.call(this);
                    };
                }''')
            page.locator('#btn-stage').click()
            if suffix:
                try:
                    page.locator('#btn-audio-retry').wait_for(state='visible', timeout=30000)
                except Exception:
                    print(page.evaluate('({load:document.querySelector("#load-txt").innerText,meta:document.querySelector("#playmeta").innerText,locked:G.locked,active:navigator.userActivation.isActive,gesture:window.requireGesture,questions:G.questions.length,state:G.questions[0]?.audio?.el.readyState})'), errors, flush=True)
                    raise
                assert page.evaluate('G.audioPermissionBlocked && G.locked && G.log.length===0')
                before = page.evaluate('G.questions[0].audio.el === G.clip.primary')
                assert before
                page.evaluate('window.preparedPrimary=G.questions[0].audio.el')
                page.locator('#btn-audio-retry').click()
                page.wait_for_function('!G.locked && G.clip instanceof DualAudioQuestion')
                assert page.evaluate('G.clip.primary===preparedPrimary && !G.audioPermissionBlocked')
                # Let both real local media elements play and check timing/ratio.
                page.wait_for_function('G.clip.triggered && !G.clip.interference.paused', timeout=7000)
                assert page.evaluate('G.clip.startedAtPrimarySeconds>=2.5 && G.clip.interference.volume===G.clip.primary.volume*.5')
                print('PASS permission denial locks question; click reuses loaded audio and starts both local streams', suffix, flush=True)
                # Secondary denial must also stop both players and offer recovery.
                page.evaluate('''() => {
                    G.clip.onError(new DOMException('Test secondary policy','NotAllowedError'));
                }''')
                assert page.evaluate('G.locked && G.clip.primary.paused && G.clip.interference.paused')
                page.locator('#btn-audio-retry').click()
                page.wait_for_function('!G.locked')
            for stage in range(1, 7):
                for index in range(10):
                    page.wait_for_function('(i)=>G.index===i && !G.locked', arg=index, timeout=15000)
                    assert page.locator('#grid button').count()==9
                    page.evaluate('''() => {
                        const q=G.questions[G.index];
                        document.querySelectorAll('#grid button')[q.options.indexOf(q.song)].click();
                    }''')
                page.locator('#pop').wait_for(state='visible')
                assert page.evaluate('G.stage')==stage
                assert page.evaluate('Store.bestStage()')==stage
                if stage<6: page.locator('#btn-stage-go').click()
            page.locator('#btn-stage-quit').click()
            assert page.locator('#screen-start').is_visible()
            assert not errors, errors
            print('PASS six stages, 60 questions, progression and return home', suffix or 'normal', flush=True)
            page.close()
        browser.close()
finally:
    server.shutdown();server.server_close()
