const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
global.window = {};
require('../songs'); require('../previews'); require('../decoys'); require('../named-decoys');
const {SONGS, SONG_PREVIEWS, DECOYS} = window;
const expansion = require('../data/library-expansion-2026-10.json');
const clean = s => s.replace(/\s*[（(【\[].*$/, '').replace(/\s+[-–—]\s+.*$/, '').trim().toLowerCase();
test('710 unique song IDs; initial expansion retains 50 songs per category', () => {
  assert.equal(SONGS.length, 710);
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
  for(const song of expansion.songs){
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
test('20 Joe Hisaishi works have eight distinct near-title distractors each', () => {
  assert.equal(hisaishi.songs.length, 20);
  assert.equal(SONGS.filter(s=>s.genre==='jp').length, 88);
  const realTitles=new Set(SONGS.map(s=>clean(s.title)));
  const sourceURLs=new Set();
  for(const source of hisaishi.songs){
    const song=SONGS.find(s=>s.id===source.id);
    assert.equal(song.artist, '久石讓');
    assert.equal(song.genre, 'jp');
    assert.equal(song.title, source.title);
    assert.equal(SONG_PREVIEWS[song.id].title, source.storeTitle);
    assert.match(source.storeArtist, /久石|Joe Hisaishi/);
    const labels=window.NAMED_DECOYS[song.id];
    assert.equal(labels.length,8);
    assert.equal(new Set(labels.map(clean)).size,8);
    assert(labels.every(title=>!realTitles.has(clean(title))));
    sourceURLs.add(SONG_PREVIEWS[song.id].url);
  }
  assert.equal(sourceURLs.size,20);
});
