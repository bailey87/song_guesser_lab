/* Build demo options from playable real songs plus per-song invented labels. */
(function(root){
  function build(answer, {songs, decoys, previews, namedDecoys, shuffle, titleKey, maxSameArtist=2}){
    const isNamed=!!namedDecoys[answer.id];
    const eligible=songs.filter(song=>song.id!==answer.id && titleKey(song.title)!==titleKey(answer.title)
      && previews[song.id]?.url && (!isNamed || namedDecoys[song.id]));
    const sameGenre=eligible.filter(s=>s.genre===answer.genre);
    const interferenceSong=shuffle(sameGenre.length?sameGenre:eligible)[0];
    if(!interferenceSong) throw new Error('沒有可播放的干擾選項');
    const options=[answer,interferenceSong];
    const used=new Set(options.map(s=>titleKey(s.title)));
    const add=option=>{
      const key=titleKey(option.title);
      if(used.has(key)) return false;
      used.add(key); options.push(option); return true;
    };
    if(isNamed){
      const answerCount=shuffle([3,4])[0];
      for(const [song,count] of [[answer,answerCount],[interferenceSong,7-answerCount]]){
        let added=0;
        for(const title of shuffle(namedDecoys[song.id])){
          if(add({title,artist:song.artist,genre:song.genre,invented:true,basedOn:song.id})) added++;
          if(added===count) break;
        }
        if(added!==count) throw new Error('近似名稱不足');
      }
    }else{
      const pool=songs.concat(decoys);
      const byArtist={}; options.forEach(s=>{byArtist[s.artist]=(byArtist[s.artist]||0)+1;});
      for(const [list,max] of [[pool.filter(s=>s.genre===answer.genre),maxSameArtist],[pool,maxSameArtist],[pool,Infinity]]){
        for(const song of shuffle(list)){
          if(options.length===9) break;
          if((byArtist[song.artist]||0)>=max) continue;
          if(add(song)) byArtist[song.artist]=(byArtist[song.artist]||0)+1;
        }
        if(options.length===9) break;
      }
    }
    if(options.length!==9) throw new Error('選項不足九個');
    return {options,interferenceSong};
  }
  root.InterferenceOptions={build};
  if(typeof module!=='undefined'&&module.exports) module.exports={build};
})(typeof window==='undefined'?globalThis:window);
