"""Run with Python Playwright installed and Chromium on PATH (or CHROMIUM_PATH)."""
import functools
import http.server
import os
from pathlib import Path
import shutil
import threading
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{server.server_port}'
try:
    with sync_playwright() as p:
        executable = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
        browser = p.chromium.launch(headless=True, executable_path=executable, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':390,'height':844})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(url, wait_until='domcontentloaded')
        assert page.locator('#library-info').inner_text().startswith('710')
        page.screenshot(path='/tmp/song-guesser-home.png')
        assert page.locator('#btn-speed').is_disabled()
        page.locator('#nick').fill('Test')
        page.locator('#btn-test').click()
        assert page.locator('#btn-speed').is_enabled()
        page.evaluate('CONFIG.revealMs = 10')
        page.locator('#btn-speed').click()
        speed_ids = page.evaluate('G.questions.map(q=>q.song.id)')
        assert len(set(speed_ids)) == 10
        def answer_round():
            for i in range(10):
                page.wait_for_function('(i)=>G.index===i && !G.locked && !document.querySelector("#screen-play").hidden', arg=i, timeout=60000)
                assert page.locator('#grid button').count() == 9
                if i == 0:
                    page.screenshot(path='/tmp/song-guesser-play.png')
                assert page.evaluate('G.questions[G.index].audio?.source') == 'preview'
                assert page.evaluate('new Set(G.questions[G.index].options.map(o=>titleKey(o.title))).size') == 9
                idx = page.evaluate('G.questions[G.index].options.indexOf(G.questions[G.index].song)')
                page.locator('#grid button').nth(idx).click()
            page.wait_for_function('G.index===10')
        answer_round()
        assert page.locator('#screen-result').is_visible()
        page.screenshot(path='/tmp/song-guesser-results.png')
        assert page.evaluate('Store.all().slice(-1)[0].correct') == 10
        assert '幹部' not in page.locator('body').inner_text()
        assert '玩家' not in page.locator('#res-meta').inner_text()
        print('PASS real streamed audio, 10 speed answers, score and local result', flush=True)
        page.reload(wait_until='domcontentloaded')
        assert len(page.evaluate('songRotation.history')) == 10
        page.evaluate('CONFIG.revealMs = 10')
        page.locator('#nick').fill('Test'); page.locator('#btn-test').click(); page.locator('#btn-stage').click()
        stage_ids = page.evaluate('G.questions.map(q=>q.song.id)')
        assert not set(speed_ids).intersection(stage_ids)
        assert page.evaluate('new Set(G.questions.map(q=>q.song.genre)).size') == 6
        assert page.evaluate('stagePool(1).length') == 710
        assert page.evaluate('stagePool(6).length') == 710
        for stage in range(1, 7):
            answer_round()
            assert page.locator('#pop').is_visible()
            assert page.evaluate('Store.bestStage()') == stage
            print(f'PASS stage {stage}: full library, 10 streamed questions and progression', flush=True)
            if stage < 6:
                page.locator('#btn-stage-go').click()
        page.locator('#btn-stage-quit').click()
        assert page.locator('#screen-start').is_visible()
        # Exercise the threshold failure branch without waiting for 10 timeouts.
        page.evaluate('G.mode="stage";G.stage=1;G.total=0;G.log=[];finishStage()')
        assert page.locator('#screen-result').is_visible()
        assert '全語系' in page.locator('#res-line').inner_text()
        page.locator('#btn-home').click()
        assert page.locator('#screen-start').is_visible()
        for genre in ['mando','classic','tw','west','kpop','jp']:
            source = page.evaluate('''async genre => {
                const q={song:SONGS.find(s=>s.genre===genre && s.id.startsWith('add_'))};
                const clip=await prepareClip(q);return clip?.source;
            }''', genre)
            assert source == 'preview', genre
        print('PASS one new real audio source per category, failure/home navigation', flush=True)
        assert not errors, errors
        browser.close()
finally:
    server.shutdown()
    server.server_close()
