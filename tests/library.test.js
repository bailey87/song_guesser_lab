const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
global.window = {};
require('../songs'); require('../previews'); require('../decoys'); require('../ghibli-themes');
const {SONGS, SONG_PREVIEWS, DECOYS} = window;
const expansion = require('../data/library-expansion-2026-10.json');
const refresh=require('../data/jp-anime-refresh.json');
const clean = s => s.replace(/\s*[（(【\[].*$/, '').replace(/\s+[-–—]\s+.*$/, '').trim().toLowerCase();
test('725 unique song IDs; initial expansion retains 50 songs per category', () => {
  assert.equal(SONGS.length, 725);
  assert.equal(new Set(SONGS.map(s => s.id)).size, SONGS.length);
  assert.equal(expansion.songs.length, 300);
  for(const genre of ['mando','classic','tw','west','kpop','jp']){
    assert.equal(expansion.songs.filter(s => s.genre === genre).length, 50);
  }
  for(const song of SONGS){
    assert(song.id && song.title && song.artist && song.genre);
    assert.equal(new URL(SONG_PREVIEWS[song.id].url).hostname, 'audio-ssl.itunes.apple.com');
  }
});
test('new Japanese/Korean and modern Mandarin selections meet date policy', () => {
  for(const song of expansion.songs.filter(s=>!s.retired)){
    assert(SONGS.some(s => s.id === song.id && s.title === song.title && s.genre === song.genre));
    assert.equal(SONG_PREVIEWS[song.id].title, song.storeTitle);
    assert(song.releaseDate <= expansion.selectionDate);
    if(['jp','kpop'].includes(song.genre)) assert(song.releaseDate >= '2021-10-22', song.title);
    if(song.genre === 'mando') assert(song.releaseDate >= '2006-10-22', song.title);
  }
});
test('decoys do not duplicate visible question titles', () => {
  const titles = new Set(SONGS.map(s => clean(s.title)));
  assert(DECOYS.every(s => !titles.has(clean(s.title))));
});
test('retired shared leaderboard is not part of the current application', () => {
  const html = fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
  assert(!/crew\.js|CREW|beatPercent|screen-board|btn-board|解鎖/.test(html));
  for(const file of ['crew.js','staff.html','board-config.js']){
    assert(!fs.existsSync(path.join(__dirname,'..',file)));
  }
});

const hisaishi = require('../data/hisaishi-20.json');
test('20 Hisaishi entries are Miyazaki film scores with canonical real options', () => {
  assert.equal(hisaishi.songs.length,20);
  assert.equal(SONGS.filter(s=>s.genre==='jp').length,103);
  const films=new Set(['風之谷','天空之城','龍貓','魔女宅急便','紅豬','魔法公主','神隱少女','霍爾的移動城堡','崖上的波妞','風起','蒼鷺與少年']);
  const sourceURLs=new Set();
  for(const source of hisaishi.songs){
    const song=SONGS.find(s=>s.id===source.id);
    assert.equal(song.artist,'久石讓');assert.equal(song.genre,'jp');assert.equal(song.title,source.title);
    assert(films.has(source.film));assert.equal(SONG_PREVIEWS[song.id].title,source.storeTitle);
    sourceURLs.add(SONG_PREVIEWS[song.id].url);
  }
  assert.equal(sourceURLs.size,20);
  const catalog=require('../data/miyazaki-themes.json');
  assert.deepEqual(window.GHIBLI_THEMES,catalog.themes);
  assert.equal(new Set(catalog.themes.map(s=>clean(s.title))).size,catalog.themes.length);
  assert(catalog.themes.every(s=>s.source && s.storeTitle && films.has(s.film)));
  assert(catalog.themes.some(s=>!s.questionId));
});
test('Japanese refresh retires 20 and adds 20 anime + 5 ONE PIECE + 10 Mrs tracks',()=>{
  assert.equal(refresh.retiredSongs.length,20);assert.equal(refresh.songs.length,35);
  assert.equal(expansion.songs.filter(s=>s.retired).length,20);
  for(const row of refresh.retiredSongs){assert(!SONGS.some(s=>s.id===row.id));assert(!SONG_PREVIEWS[row.id]);}
  for(const [kind,n] of [['anime',20],['one-piece',5],['mrs-green-apple',10]]){
    const group=refresh.songs.filter(s=>s.category===kind);assert.equal(group.length,n);
    for(const row of group){
      assert(SONGS.some(s=>s.id===row.id && s.title===row.title));
      assert.equal(SONG_PREVIEWS[row.id].title,row.storeTitle);
      assert(row.releaseDate>='2006-10-22' && row.releaseDate<='2026-10-22');
      if(kind==='anime'){assert(row.anime && row.workReleaseYear>=2006);}
      if(kind==='one-piece')assert(refresh.onePieceDrawPool.includes(row.title));
      if(kind==='mrs-green-apple')assert(refresh.mrsDrawPool.includes(row.title));
    }
  }
});
