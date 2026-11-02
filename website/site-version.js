/* Public release display only; desktop installation keeps its own signature checks. */
(()=>{
  const endpoint='https://api.xueluosh.top/jingban/latest.json',cacheKey='jingban.public-version.v2';
  const valid=v=>typeof v==='string'&&v.length<=50&&/^\d+(?:\.\d+){1,3}(?:[-+][a-z0-9.-]+)?$/i.test(v);
  let current=null,lastAttempt=0,inFlight=null;
  function compare(a,b){
    const aa=a.split(/[-+]/)[0].split('.').map(Number),bb=b.split(/[-+]/)[0].split('.').map(Number);
    for(let i=0;i<Math.max(aa.length,bb.length);i++){const n=(aa[i]||0)-(bb[i]||0);if(n)return Math.sign(n);}
    return a.includes('-')!==b.includes('-')?(a.includes('-')?-1:1):0;
  }
  function show(info,mode){
    if(info){current=info;document.querySelectorAll('[data-current-version]').forEach(e=>e.textContent='v'+info.version);}
    document.querySelectorAll('[data-update-version]').forEach(e=>e.textContent=info?.updateVersion?'v'+info.updateVersion:'暂不可查询');
    document.documentElement.dataset.versionMode=mode;
    const status=mode==='live'?'已同步安装包与联网更新信息':mode==='partial'?(info?.packageVersion?'安装包已同步；联网更新暂不可查询':'联网更新已同步；安装包信息暂不可查询'):mode==='cached'?'显示上次查询的发布信息':mode==='loading'?'正在查询发布信息…':'暂时无法查询发布信息';
    document.querySelectorAll('[data-version-state]').forEach(e=>e.textContent=status);
    document.querySelectorAll('[data-version-refresh]').forEach(e=>e.disabled=mode==='loading');
    document.querySelectorAll('[data-version-checked]').forEach(e=>e.textContent=info?.checkedAt?new Intl.DateTimeFormat('zh-CN',{hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(info.checkedAt)):'');
    if(info)document.dispatchEvent(new CustomEvent('jingban:version',{detail:{...info,mode}}));
  }
  try{const saved=JSON.parse(localStorage.getItem(cacheKey)||'null');if(saved&&valid(saved.version)&&(!saved.updateVersion||valid(saved.updateVersion))&&(!saved.packageVersion||valid(saved.packageVersion))&&Number.isFinite(saved.checkedAt)&&saved.checkedAt<=Date.now()+60000)show(saved,'cached');}catch{}
  async function readJson(url,limit,signal){
    const response=await fetch(url,{cache:'no-store',credentials:'omit',signal});
    if(!response.ok)throw Error('Release information unavailable');
    const raw=await response.text();if(raw.length>limit)throw Error('Response too large');return JSON.parse(raw);
  }
  function refresh(){
    if(inFlight)return inFlight;
    lastAttempt=Date.now();show(current,'loading');
    inFlight=(async()=>{
      const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),10000);
      try{
        const results=await Promise.allSettled([
          readJson(endpoint,2*1024*1024,controller.signal).then(e=>{const p=e?.payload??e;if(!valid(p?.version))throw Error('Invalid updater version');return p.version;}),
          readJson('release.json',32768,controller.signal).then(r=>{
            if(r?.published!==true)return null;
            if(typeof r.url!=='string'||!r.url||!valid(r.version)||!Number.isSafeInteger(r.bytes)||r.bytes<=0||typeof r.sha256!=='string'||!/^[a-f0-9]{64}$/i.test(r.sha256))throw Error('Invalid package release');
            if(!['https:','http:'].includes(new URL(r.url,location.href).protocol))throw Error('Invalid package URL');
            return r.version;
          })
        ]);
        const updateVersion=results[0].status==='fulfilled'?results[0].value:null,packageVersion=results[1].status==='fulfilled'?results[1].value:null;
        const versions=[updateVersion,packageVersion].filter(Boolean);if(!versions.length)throw Error('No version available');
        const info={version:versions.reduce((a,b)=>compare(a,b)>=0?a:b),updateVersion,packageVersion,checkedAt:Date.now()};
        show(info,results.every(r=>r.status==='fulfilled')?'live':'partial');
        try{localStorage.setItem(cacheKey,JSON.stringify(info));}catch{}return info;
      }catch{show(current,current?'cached':'unavailable');return current;}
      finally{clearTimeout(timeout);inFlight=null;}
    })();return inFlight;
  }
  document.querySelectorAll('[data-version-refresh]').forEach(b=>b.addEventListener('click',refresh));
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&Date.now()-lastAttempt>15000)refresh();});
  setInterval(()=>{if(!document.hidden)refresh();},60000);
  window.JingbanVersion={refresh,compare,get current(){return current;}};refresh();
})();
