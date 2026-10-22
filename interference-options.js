/* Real-song options; Hisaishi questions use actual Miyazaki film themes. */
(function(root){
  function build(answer, {songs, decoys, previews, themeOptions, shuffle, titleKey, maxSameArtist=2}){
    const isHisaishi=answer.artist==='久石讓';
    const workOf=song=>themeOptions.find(t=>t.questionId===song.id)?.workKey || song.id;
    const usedWorks=new Set([workOf(answer)]);
    const eligible=songs.filter(song=>song.id!==answer.id && titleKey(song.title)!==titleKey(answer.title)
      && previews[song.id]?.url && (!isHisaishi || (song.artist==='久石讓' && workOf(song)!==workOf(answer))));
    const sameGenre=eligible.filter(s=>s.genre===answer.genre);
    const interferenceSong=shuffle(sameGenre.length?sameGenre:eligible)[0];
    if(!interferenceSong) throw new Error('沒有可播放的干擾選項');
    const options=[answer,interferenceSong];
    usedWorks.add(workOf(interferenceSong));
    const used=new Set(options.map(s=>titleKey(s.title)));
    const add=option=>{
      const key=titleKey(option.title);
      if(used.has(key)) return false;
      used.add(key); options.push(option); return true;
    };
    if(isHisaishi){
      for(const theme of shuffle(themeOptions)){
        if(options.length===9) break;
        if(usedWorks.has(theme.workKey)) continue;
        if(add({title:theme.title,artist:theme.artist,genre:'jp',themeFilm:theme.film,themeOption:true})) usedWorks.add(theme.workKey);
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
