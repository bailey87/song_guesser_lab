const test = require('node:test');
const assert = require('node:assert/strict');
const SongRotation = require('../song-rotation');
const makeSongs = (genres = ['a', 'b'], perGenre = 20) => genres.flatMap(genre =>
  Array.from({length:perGenre}, (_, i) => ({id:`${genre}${i}`, genre})));
function memory(initial){
  const values = new Map(initial);
  return {getItem:key => values.get(key) ?? null, setItem:(key, value) => values.set(key, value)};
}
test('unseen songs are exhausted before repeats; oldest songs return first', () => {
  const songs = makeSongs(['a'], 20), rotation = new SongRotation(null);
  const first = rotation.draw(songs, 10);
  first.forEach(s => rotation.record(s.id, songs));
  const second = rotation.draw(songs, 10);
  assert.equal(new Set([...first, ...second].map(s => s.id)).size, 20);
  second.forEach(s => rotation.record(s.id, songs));
  assert.deepEqual(rotation.draw(songs, 10).map(s => s.id), first.map(s => s.id));
});
test('rotation survives reload and works across game modes sharing storage', () => {
  const storage = memory(), songs = makeSongs();
  const speed = new SongRotation(storage);
  const first = speed.draw(songs, 10, {a:1, b:1});
  first.forEach(s => speed.record(s.id, songs));
  const stage = new SongRotation(storage), next = stage.draw(songs, 10, {a:1, b:1});
  assert(next.every(s => !first.some(old => old.id === s.id)));
  assert(next.some(s => s.genre === 'a') && next.some(s => s.genre === 'b'));
});
test('small categories reuse oldest entries without duplicate questions or starvation', () => {
  const songs = [...makeSongs(['a'], 2), ...makeSongs(['b'], 30)];
  const rotation = new SongRotation(null), seenB = new Set();
  for(let round = 0; round < 5; round++){
    const draw = rotation.draw(songs, 6, {a:1,b:1});
    assert.equal(new Set(draw.map(s => s.id)).size, 6);
    assert(draw.some(s => s.genre === 'a'));
    for(const song of draw){
      if(song.genre === 'b'){ assert(!seenB.has(song.id)); seenB.add(song.id); }
      rotation.record(song.id, songs);
    }
  }
});
test('abandoned draws do not consume songs and removed IDs are pruned', () => {
  const storage = memory([['songguesser_rotation_v1', '["removed","a0","a0"]']]);
  const rotation = new SongRotation(storage), songs = makeSongs(['a']);
  const before = rotation.history.slice();
  rotation.draw(songs, 10);
  assert.deepEqual(rotation.history, before);
  rotation.record('a1', songs);
  assert.deepEqual(rotation.history, ['a0','a1']);
});
test('malformed or unavailable storage does not prevent gameplay', () => {
  const songs = makeSongs();
  for(const storage of [memory([['songguesser_rotation_v1','{}']]), memory([['songguesser_rotation_v1','invalid']]), {getItem(){throw Error('blocked')},setItem(){throw Error('full')}}]){
    const rotation = new SongRotation(storage);
    const draw = rotation.draw(songs, 10);
    draw.forEach(s => rotation.record(s.id, songs));
    assert.equal(rotation.history.length, 10);
    assert.throws(() => rotation.draw(songs, 100), /題庫歌曲不足/);
  }
});
