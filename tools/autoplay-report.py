"""Play real browser rounds and save a reproducible song-draw report.

Requires Python Playwright and Chromium. Uses a fresh browser context. Only
answer-reveal pauses are shortened; drawing, playback and scoring are real.
"""
import argparse
from collections import Counter
from datetime import datetime
import functools
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
LABELS = {'mando':'現代華語','classic':'華語經典','tw':'台語','west':'西洋','kpop':'韓文','jp':'日文'}
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--rounds', type=int, default=10)
parser.add_argument('--url', help='Optional deployed game URL; otherwise serve the current checkout locally')
parser.add_argument('--output', type=Path, default=ROOT/'docs/playtests/autoplay-10-rounds.json')
args = parser.parse_args()
if args.rounds < 1:
    parser.error('--rounds must be positive')
server = None
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass
if args.url:
    url = args.url
else:
    server = http.server.ThreadingHTTPServer(('127.0.0.1',0), functools.partial(QuietHandler,directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}'
report = {
    'startedAt':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),
    'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    'target':args.url or 'Current checkout served locally; not a deployment verification',
    'method':'Real Chromium audio; wait for playback progress or until 3 seconds remain, then auto-select correct answers; revealMs=10; fresh storage; reload after round 5',
    'rounds':[],
}
try:
    with sync_playwright() as p:
        executable = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
        browser = p.chromium.launch(headless=True, executable_path=executable,args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':390,'height':844})
        errors = []
        failures = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('requestfailed', lambda r: failures.append({'url':r.url,'error':r.failure}))
        page.goto(url,wait_until='domcontentloaded')
        for number in range(1,args.rounds+1):
            if number == 6:
                page.reload(wait_until='domcontentloaded')
            page.evaluate('CONFIG.revealMs=10')
            page.locator('#nick').fill('AutoTest')
            if not page.evaluate('G.soundOk'):
                page.locator('#btn-test').click()
            page.locator('#btn-speed').click()
            print('Draw '+str(number)+': '+json.dumps(page.evaluate('G.questions.map(q=>q.song.title)'),ensure_ascii=False),flush=True)
            # Observe and answer atomically inside the page. Cross-process UI
            # calls can otherwise race a timeout or a rapid question transition.
            page.evaluate('''() => {
                window.autoplayObserved = new Map();
                window.autoplayTimer = setInterval(() => {
                    if(G.index >= G.questions.length){ clearInterval(window.autoplayTimer); return; }
                    if(G.locked || document.querySelector('#screen-play').hidden) return;
                    const q=G.questions[G.index];
                    if(window.autoplayObserved.has(G.index)) return;
                    const el=q.audio?.el;
                    const started=!!el && !el.paused && el.currentTime>0;
                    // Record stalled playback honestly; do not wait past expiry.
                    if(!started && G.deadline-performance.now()>3000) return;
                    window.autoplayObserved.set(G.index, {...q.song,
                        source:q.audio?.source || 'synth',
                        playbackSeconds:el?.currentTime || 0,
                        optionCount:q.options.length});
                    document.querySelectorAll('#grid button')[q.options.indexOf(q.song)].click();
                }, 50);
            }''')
            try:
                page.wait_for_function('!document.querySelector("#screen-result").hidden && G.index===10',timeout=180000)
            except Exception:
                diagnostic=page.evaluate('({index:G.index,locked:G.locked,screen:SCREENS.find(s=>!document.getElementById(s).hidden),load:document.querySelector("#load-txt").textContent})')
                diagnostic.update({'round':number,'errors':errors,'requestFailures':failures[-8:]})
                Path('/tmp/autoplay-failure.json').write_text(json.dumps(diagnostic,ensure_ascii=False,indent=2))
                print('FAILURE '+json.dumps(diagnostic,ensure_ascii=False),flush=True)
                raise
            songs = page.evaluate('Array.from(autoplayObserved.values())')
            assert len(songs)==10, 'Automation missed a question transition'
            assert all(s['optionCount']==9 for s in songs)
            result = page.evaluate('({score:G.total,correct:G.log.filter(r=>r.correct).length,historyCount:songRotation.history.length})')
            assert result['correct'] == 10
            assert len({s['genre'] for s in songs}) == 6
            report['rounds'].append({'round':number,'songs':songs,**result})
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.with_suffix('.partial.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            print(f'Round {number}: '+ ' / '.join(s['title'] for s in songs),flush=True)
            page.locator('#btn-home').click()
        assert not errors, errors
        browser.close()
    all_songs = [s for r in report['rounds'] for s in r['songs']]
    ids = Counter(s['id'] for s in all_songs)
    report['summary'] = {
        'completedRounds':len(report['rounds']),'questions':len(all_songs),'uniqueSongs':len(ids),
        'repeatAppearances':sum(n-1 for n in ids.values()),
        'genreCounts':dict(Counter(s['genre'] for s in all_songs)),
        'allRealAudioPlayback':all(s['source']=='preview' and s['playbackSeconds']>0 for s in all_songs),
        'confirmedPlaybackQuestions':sum(s['source']=='preview' and s['playbackSeconds']>0 for s in all_songs),
        'unconfirmedPlaybackSongs':[{'round':r['round'],'question':i,'id':s['id'],'title':s['title']} for r in report['rounds'] for i,s in enumerate(r['songs'],1) if s['source']!='preview' or s['playbackSeconds']<=0],
        'javascriptErrors':errors,
    }
    report['completedAt'] = datetime.now(ZoneInfo('Asia/Taipei')).isoformat()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.with_suffix('.partial.json').unlink(missing_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# 十輪自動試玩紀錄','',
        f"測試時間：{report['startedAt']}（台北時間）。程式版本：`{report['commit'][:7]}`。",'',
        '測試對象為目前 checkout 的本機版本，這份結果不能證明 GitHub Pages 已部署完成。' if not args.url else f'測試網址：{args.url}', '',
        '使用全新瀏覽器紀錄，連續玩十場競速，中途第五場後重新整理。每題使用遊戲本身的音源載入流程，優先等播放器前進後自動選正解；若只剩三秒仍無進度，會記錄未確認播放並作答。僅將揭曉停頓由 2200 ms 縮短為 10 ms。這是播放與流程測試，不是逐首聽辨／難度評測。','',
        f"結果：完成 {len(report['rounds'])} 輪、{len(all_songs)} 題、{len(ids)} 首不同歌曲，重複出現 {report['summary']['repeatAppearances']} 次；JavaScript 錯誤 {len(errors)}。",'',
        f"音訊：{report['summary']['confirmedPlaybackQuestions']}/{len(all_songs)} 題觀察到真實預覽播放進度；{len(report['summary']['unconfirmedPlaybackSongs'])} 題在作答前未確認進度。後者可能是緩衝、預載／狀態時序或播放問題，尚未單獨確認原因，不能解讀為全部音訊通過。",'',
        '| 分類 | 次數 |','| --- | ---: |']
    lines.extend(f'| {LABELS[g]} | {report["summary"]["genreCounts"].get(g,0)} |' for g in LABELS)
    lines.extend(['','## 未確認播放進度的題目','','| 輪次 | 題號 | 歌曲 |','| ---: | ---: | --- |'])
    lines.extend(f'| {x["round"]} | {x["question"]} | {x["title"]} |' for x in report['summary']['unconfirmedPlaybackSongs'])
    for r in report['rounds']:
        lines.extend(['',f'## 第 {r["round"]} 輪','',f'答對 {r["correct"]}/10；得分 {r["score"]:,}。','',
            '| 題號 | 歌曲 | 歌手 | 分類 | 音訊進度 |','| ---: | --- | --- | --- | --- |'])
        lines.extend(f'| {i} | {s["title"].replace("|","／")} | {s["artist"].replace("|","／")} | {LABELS[s["genre"]]} | {"已確認" if s["source"]=="preview" and s["playbackSeconds"]>0 else "未確認"} |' for i,s in enumerate(r['songs'],1))
    lines.extend(['','完整逐題資料見同目錄 JSON（含歌曲 ID、播放器時間與輪替紀錄數）。',''])
    args.output.with_suffix('.md').write_text('\n'.join(lines))
    print(json.dumps(report['summary'],ensure_ascii=False),flush=True)
finally:
    if server:
        server.shutdown();server.server_close()
