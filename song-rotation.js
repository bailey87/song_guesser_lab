/* Persistent least-recently-played rotation, shared by both game modes.
 * Only displayed questions are recorded; preloading and abandoned draws do
 * not consume songs. Unknown/old IDs are pruned when the library changes.
 */
(function(root){
  class SongRotation {
    constructor(storage, random = Math.random){
      if(storage === undefined){
        try{ storage = root.localStorage; }catch(e){ storage = null; }
      }
      this.storage = storage;
      this.random = random;
      this.key = 'songguesser_rotation_v1';
      this.history = [];
      try{
        const saved = JSON.parse(storage && storage.getItem(this.key));
        if(Array.isArray(saved)) this.history = [...new Set(saved.filter(id => typeof id === 'string'))];
      }catch(e){}
    }
    draw(songs, count, floor = {}){
      if(!Number.isInteger(count) || count < 1 || songs.length < count){
        throw new Error('題庫歌曲不足，無法產生完整回合');
      }
      const rank = new Map(this.history.map((id, i) => [id, i]));
      const candidates = songs.slice();
      for(let i = candidates.length - 1; i > 0; i--){
        const j = Math.floor(this.random() * (i + 1));
        [candidates[i], candidates[j]] = [candidates[j], candidates[i]];
      }
      // Stable sort keeps unseen songs randomly ordered, then oldest first.
      candidates.sort((a, b) => (rank.get(a.id) ?? -1) - (rank.get(b.id) ?? -1));
      const picked = [], used = new Set();
      const take = (pool, n) => {
        for(const song of pool){
          if(n <= 0 || picked.length >= count) break;
          if(used.has(song.id)) continue;
          picked.push(song); used.add(song.id); n--;
        }
      };
      for(const [key, n] of Object.entries(floor || {})){
        const genres = key.split('+');
        take(candidates.filter(s => genres.includes(s.genre)), n);
      }
      take(candidates, count - picked.length);
      return picked;
    }
    record(id, songs){
      const known = new Set(songs.map(s => s.id));
      if(!known.has(id)) return;
      this.history = this.history.filter(old => old !== id && known.has(old));
      this.history.push(id);
      try{ if(this.storage) this.storage.setItem(this.key, JSON.stringify(this.history)); }catch(e){}
    }
  }
  root.SongRotation = SongRotation;
  if(typeof module !== 'undefined' && module.exports) module.exports = SongRotation;
})(typeof window === 'undefined' ? globalThis : window);
