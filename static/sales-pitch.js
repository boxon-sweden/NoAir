'use strict';
// Shared by the original contact preview and the editable outreach queue.
// Keep the server copy in outreach.draft_for in sync (covered by browser tests).
window.noairSalesDrafts = report => {
  const products=[['hörlurar(?:na)?','hörlurar'],['headset(?:et)?','ett headset'],['laddare(?:n)?','en laddare'],['mobilskal(?:et)?','ett mobilskal'],['tangentbord(?:et)?','ett tangentbord'],['datormus(?:en)?','en datormus'],['kab(?:el|eln|lar|larna)','kablar'],['skor(?:na)?','skor'],['kläder(?:na)?','kläder'],['tröj(?:a|an|or|orna)','en tröja'],['bok(?:en)?|böcker(?:na)?','böcker']];
  const comment=(report.comment||'').replace(/\S+@\S+|https?:\/\/\S+/gi,match=>' '.repeat(match.length));
  const candidates=[];
  products.forEach(([pattern,label])=>{
    const regex=new RegExp('(?<![\\p{L}\\p{N}_])(?:'+pattern+')(?![\\p{L}\\p{N}_])','giu');
    for(const match of comment.matchAll(regex)){
      const start=Math.max(...['.','!','?','\n'].map(mark=>comment.lastIndexOf(mark,match.index-1)))+1;
      const prefix=comment.slice(start,match.index);
      if(/\b(inte|ingen|inget|inga|istället för|i stället för|som om|till exempel|exempelvis|skulle|kunde|kanske)\b/i.test(prefix))continue;
      candidates.push([match.index,label]);
    }
  });
  candidates.sort((a,b)=>a[0]-b[0]);
  const product=candidates[0]?.[1]||'';
  const company=String(report.company).replace(/[\r\n\x00-\x1f]/g,' ').trim();
  const selected=new Set(report.issues);
  const category={'Elektronik':'elektronik','Kläder & skor':'kläder eller skor','Hem & inredning':'hem- och inredningsprodukter','Sport & fritid':'sport- och fritidsprodukter'}[report.category]||'';
  const delivery=product?'en leverans med '+product:(category?'en leverans av '+category:'en leverans');
  const observations=[];
  if(selected.has('oversized'))observations.push('att lådan var stor i förhållande till innehållet');
  if(selected.has('air'))observations.push('att det fanns mycket tomrum i paketet');
  if(selected.has('filler'))observations.push('att det användes mycket fyllnadsmaterial');
  if(selected.has('protection'))observations.push('att produkten inte upplevdes vara tillräckligt skyddad');
  const observation=observations.length?observations.slice(0,2).join(' och '):'att förpackningen kunde vara bättre anpassad till innehållet';
  const insight=`Via Noair, Boxons initiativ för att fånga upp konsumenters leveransupplevelser, har vi fått en rapport från en av era kunder om ${delivery} från ${company}. Kunden beskriver ${observation}.`;
  let proposal;
  if(selected.has('protection'))proposal='en lösning med bättre passform och anpassad stötdämpning, där vi utvärderar skyddet för produkten';
  else if(selected.has('air')||selected.has('oversized'))proposal='ett mindre lådformat och en anpassad insats, med rätt skydd för innehållet';
  else if(selected.has('filler'))proposal='bättre passform och en anpassad insats som kan minska behovet av fyllnadsmaterial';
  else proposal='ett mer anpassat format, material och produktskydd';
  const expertise='Vi på Boxon är specialister på att skräddarsy förpackningar efter produkten och hur den ska levereras.';
  const offer=`I det här fallet skulle vi vilja undersöka ${proposal}.`;
  const value='Målet är en mer genomtänkt uppackning för kunden och mindre onödigt emballage för er.';
  const cost='Kundunikt behöver inte bli dyrt. Vi jämför gärna ett anpassat alternativ med dagens lösning, både i funktion och kostnad.';
  const meeting='Har du 15 minuter nästa vecka? Jag visar gärna hur vi skulle ta oss an just den här leveransen och undersöka om vi kan erbjuda er en bättre lösning.';
  const referral='Om någon annan ansvarar för emballageinköp hos er får du gärna hänvisa mig rätt.';
  const variants=[
    {subject:`En kundinsikt om era förpackningar, ${company}`,body:`Hej!\n\n${insight}\n\n${expertise} ${offer} ${value}\n\n${cost}\n\n${meeting}\n\n${referral}`},
    {subject:`Kan nästa paket från ${company} ge ett bättre intryck?`,body:`Hej!\n\nEn bra produkt förtjänar en leverans som känns lika genomtänkt. ${insight}\n\n${expertise} ${offer} Det kan vara en möjlighet att förbättra kundupplevelsen redan när paketet öppnas.\n\n${cost}\n\nKan vi boka ett kort möte på 15 minuter nästa vecka och titta på vad Boxon skulle kunna göra för er?\n\n${referral}`},
    {subject:`15 minuter om ett mer anpassat paket hos ${company}?`,body:`Hej!\n\n${insight}\n\nJag hör av mig från Boxon, där vi hjälper företag med kundunika förpackningslösningar. ${offer} Ambitionen är att göra förpackningen till en bättre del av kundupplevelsen.\n\nSkräddarsytt behöver inte betyda en dyrare lösning. Låt oss börja med att se vad som är möjligt för just er produkt och era volymer.\n\nPassar ett första samtal på 15 minuter nästa vecka? Då kan vi utgå från den här leveransen och prata om ett konkret alternativ från Boxon.\n\n${referral}`}
  ];
  return variants.map(v=>({...v,body:v.body+'\n\nVänliga hälsningar,\nMarcus Gustafsson\nBoxon'}));
};
