"""Small authenticated web host for imported DSH overlays; original code stays intact."""

PET_CLIENT = r'''
import * as React from 'react';
import * as JSX from 'react/jsx-runtime';
import * as ReactDOM from 'react-dom';
import {createRoot} from 'react-dom/client';
const sections=document.querySelector('#sections');
const overlays=document.querySelector('#overlays');
const dictionaries={};
const services={commandUi:{decorate:()=>()=>{}},remote:{commands:{execute:async()=>{throw Error('此宿主没有DSH命令会话，请使用插件自身菜单。');}}}};
const primitives=new Proxy({}, {get:()=>props=>React.createElement('span',props,'◇')});
const require=name=>{
  const map={'react':React,'react/jsx-runtime':JSX,'react-dom':ReactDOM,'react-dom/client':{createRoot},'@deepseek-ai/dsh-client-ui-primitives':primitives};
  if(!map[name])throw Error('未适配前端模块：'+name);return map[name];
};
window.__ModuleLoader__={load({factory}){
 const plugin=factory(require);
 const context={effect:f=>f(),provide:(k,v)=>{services[k]=v;},get:k=>services[k],...services,
  locale:{register:(ns,value)=>{dictionaries[ns]=value.zh||{};return ()=>{};},
    bind:ns=>(key,args)=>{let s=dictionaries[ns]?.[key]||key;for(const [k,v]of Object.entries(args||{}))s=String(s).replaceAll('{'+k+'}',v);return s;}},
  slots:{register:(meta,component)=>({meta,component}),entries:()=>[],
    inject:(name,generate)=>{for(const row of generate()){
      const node=document.createElement('div');(name==='shell.overlay'?overlays:sections).append(node);
      createRoot(node).render(React.createElement(row.component,row.meta.inject?.()||{}));
    }return ()=>{};}}};
 plugin.apply(context);
}};
'''


WEB_HOST = r'''
import {createServer, request as httpRequest} from 'node:http';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {dirname,join,delimiter} from 'node:path';
import {randomBytes,timingSafeEqual} from 'node:crypto';
import {createRequire} from 'node:module';
const baseHtml='<!doctype html><meta charset="utf-8"><title>鲸伴 · 插件网页</title>'+
 '<style>body{background:#f7f9fd;color:#3c4a61;font:14px system-ui;margin:0;padding:20px}h2{font-size:18px}#sections{max-width:1000px;margin:auto}#overlays{position:fixed;inset:0;pointer-events:none}#overlays>*{pointer-events:auto}</style>'+
 '<main id="root"><div data-composer-seat="jingban"><h2>鲸伴 · 插件挂件</h2><p>已连接鲸伴界面宿主。角色、菜单与余额面板由原插件提供。</p></div>'+
 '<main id="sections"></main><div id="overlays"></div></main>';
const widgetHtml='<!doctype html><meta charset="utf-8"><title>鲸伴 · 透明挂件</title>'+
 '<style>html,body{background:transparent!important;margin:0!important;padding:0!important;overflow:hidden;font:14px system-ui}'+
 '#root>[data-composer-seat],#sections{display:none!important}#overlays{position:fixed;inset:0;pointer-events:none}#overlays>*{pointer-events:auto}</style>'+
 '<main id="root"><div data-composer-seat="jingban" hidden></div><main id="sections"></main><div id="overlays"></div></main>';
export async function createWeb(request,root,send){
 const token=randomBytes(32).toString('base64url'), routes=[], taps=[], waiting=new Map();
 let port=0,closed=false,bundle='',webVisible=false;
 // esbuild-wasm's Node API spawns "node" by name. Use the exact runtime
 // directory of this host, also when createWeb is called outside our launcher.
 if(request.petWeb){
   const pathKey=Object.keys(process.env).find(k=>k.toUpperCase()==='PATH');
   const inherited=pathKey?process.env[pathKey]:'';
   if(process.platform==='win32')for(const k of Object.keys(process.env)){
     if(k.toUpperCase()==='PATH'&&k!=='PATH')delete process.env[k];
   }
   process.env.PATH=dirname(process.execPath)+delimiter+(inherited||'');
   const require=createRequire(join(request.dependencyRoot,'package.json'));
   const esbuild=require('esbuild-wasm');
   try{
     const built=await esbuild.build({stdin:{contents:request.petClient,resolveDir:request.dependencyRoot},bundle:true,platform:'browser',format:'iife',
       define:{'process.env.NODE_ENV':'"production"'},write:false,logLevel:'silent'});bundle=built.outputFiles[0].text;
   }finally{await esbuild.stop();}
 }
 const cookie=()=> 'jb_dsh_'+port;
 const equal=(a,b)=>typeof a==='string'&&a.length===b.length&&timingSafeEqual(Buffer.from(a),Buffer.from(b));
 const authorized=req=>String(req.headers.cookie||'').split(';').some(s=>s.trim()===cookie()+'='+token);
 const fence=req=>{const origin='http://127.0.0.1:'+port;
   return req.headers.host!==('127.0.0.1:'+port)||req.headers['sec-fetch-site']==='cross-site'||
    (req.headers.origin&&req.headers.origin!==origin)||!authorized(req)?403:false;};
 const requestBalance=()=>new Promise((resolve,reject)=>{
   const id=randomBytes(12).toString('hex'),timer=setTimeout(()=>{waiting.delete(id);reject(Error('鲸伴余额查询超时'));},18000);
   waiting.set(id,{resolve,reject,timer});send('balance-request',id);
 });
 const reply=m=>{const p=waiting.get(m.id);if(!p)return;clearTimeout(p.timer);waiting.delete(m.id);
   m.result?.error?p.reject(Error(m.result.error)):p.resolve(m.result);};
 const interfaceState=()=>{
   const s=JSON.parse(readFileSync(request.interfaceFile,'utf8'));
   if(s.pid!==process.pid||!Number.isInteger(s.port)||typeof s.token!=='string'||s.token.length!==43)throw Error('桌宠服务尚未就绪');return s;
 };
 async function petApi(path,body){const s=interfaceState();return new Promise((resolve,reject)=>{
   const data=body===undefined?null:JSON.stringify(body);const r=httpRequest({hostname:'127.0.0.1',port:s.port,
    path:'/dsh-pet-7340/'+path,method:data?'POST':'GET',headers:{'x-dsh-pet-token':s.token,
     ...(data?{'content-type':'application/json','content-length':Buffer.byteLength(data)}:{})}},res=>{
      const chunks=[];let size=0;res.on('data',b=>{size+=b.length;if(size>1048576)r.destroy(Error('响应过大'));else chunks.push(b);});
      res.on('error',reject);res.on('end',()=>{try{const value=JSON.parse(Buffer.concat(chunks));
        if(res.statusCode!==200||value?.ok===false||value?.error)throw Error('桌宠操作未成功');resolve(value);
      }catch{reject(Error('桌宠响应无效或操作未成功'));}});});
    r.setTimeout(3000,()=>r.destroy(Error('桌宠请求超时')));r.on('error',reject);r.end(data);});}
 const server=createServer(async(req,res)=>{
  try{
   const origin='http://127.0.0.1:'+port;
   if(req.headers.host!=='127.0.0.1:'+port||req.headers['sec-fetch-site']==='cross-site'||(req.headers.origin&&req.headers.origin!==origin)){
    res.writeHead(403);res.end('Forbidden');return;}
   const path=new URL(req.url,origin).pathname;
   res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');
   if(!authorized(req)){
    if(path==='/__pair'&&req.method==='POST'){
      let body='';for await(const c of req){body+=c;if(body.length>200){res.writeHead(413);res.end();return;}}
      if(!equal(body,token)){res.writeHead(403);res.end();return;}
      res.setHeader('Set-Cookie',cookie()+'='+token+'; HttpOnly; SameSite=Strict; Path=/');res.end('ok');return;
    }
    if(path==='/'&&req.method==='GET'){
      res.setHeader('Content-Type','text/html; charset=utf-8');res.end('<meta charset="utf-8">'+
       (request.whaleWidget?'<style>html,body{background:transparent!important;margin:0;padding:0}</style>':'<p>正在连接插件界面…</p>')+'<script>'+ 
       'const t=new URLSearchParams(location.hash.slice(1)).get("token");history.replaceState(null,"","/");'+
       'if(t)fetch("/__pair",{method:"POST",body:t}).then(r=>{if(r.ok)location.reload();else document.body.textContent="连接已过期，请从鲸伴重新打开。"});'+
       'else document.body.textContent="请从鲸伴插件页打开此界面。";</script>');return;
    }
    res.writeHead(403);res.end('Not paired');return;
   }
   if(path==='/'&&req.method==='GET'){
    let html=request.whaleWidget?widgetHtml:baseHtml;
    if(request.petWeb)html+='<script src="/__pet-bridge.js"></script><script src="/__pet-client.js"></script>';
    for(const tap of taps)html=await tap(html);
    if(root){const table=[];root.emit('webserver/index-inject',table);
      if(!html.includes('/dsh-whale/widget.js'))for(const row of table){if(row.kind==='script'&&typeof row.text==='string')html+='<script>'+row.text+'</script>';}}
    res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html);return;
   }
   if(path==='/__pet-bridge.js'&&request.petWeb){res.setHeader('Content-Type','application/javascript');res.end(bundle);return;}
   if(path==='/__pet-client.js'&&request.petWeb){res.setHeader('Content-Type','application/javascript');res.end(readFileSync(join(dirname(request.entry),'client.js')));return;}
   if(request.petWeb&&path.startsWith('/dsh-pet-7340/')){
    const state=interfaceState();const headers={'x-dsh-pet-token':state.token};
    if(req.headers['content-type'])headers['content-type']=req.headers['content-type'];
    for(const h of ['range','if-range'])if(req.headers[h])headers[h]=req.headers[h];
    const p=httpRequest({hostname:'127.0.0.1',port:state.port,path:req.url,method:req.method,headers},r=>{
      const out={'Content-Type':r.headers['content-type']||'application/octet-stream'};
      for(const h of ['content-length','content-range','accept-ranges'])if(r.headers[h])out[h]=r.headers[h];
      res.writeHead(r.statusCode,out);r.pipe(res);});
    res.on('close',()=>p.destroy());
    p.setTimeout(20000,()=>p.destroy());p.on('error',()=>{if(!res.headersSent)res.writeHead(502);res.end();});
    let size=0;req.on('data',c=>{size+=c.length;if(size>10*1048576){p.destroy();req.destroy();}else p.write(c);});req.on('end',()=>p.end());return;
   }
   const route=routes.find(r=>r.kind==='exact'?r.path===path:path===r.path||path.startsWith(r.path+'/'));
   if(!route){res.writeHead(404);res.end('此接口尚未适配');return;}
   await route.handler(req,res);
  }catch{if(!res.headersSent)res.writeHead(500);res.end('插件界面暂不可用，请查看鲸伴插件记录。');}
 });
 server.requestTimeout=30000;server.headersTimeout=10000;
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});port=server.address().port;
 mkdirSync(dirname(request.webInterface),{recursive:true});writeFileSync(request.webInterface,JSON.stringify({pid:process.pid,port,token}));
 if(root){
   root.provide('webServer',{register:route=>{routes.push(route);return ()=>{const i=routes.indexOf(route);if(i>=0)routes.splice(i,1);};},
      tapIndex:tap=>{taps.push(tap);return ()=>{const i=taps.indexOf(tap);if(i>=0)taps.splice(i,1);};}});
   root.provide('connection',{requestRejection:fence});
   root.provide('credentials',{resolve:async()=>null,set:async()=>{throw Error('请在鲸伴设置中管理模型密钥');},delete:async()=>{throw Error('请在鲸伴设置中管理模型密钥');}});
   root.provide('deepseekAccount',{getState:()=>({userId:'jingban-local-api'}),getBalance:async()=>{
     const result=await requestBalance();return {status:'ready',value:(result.balance_infos||[]).map(r=>({currency:r.currency,balance:r.topped_up_balance})),
       bonusWallets:(result.balance_infos||[]).map(r=>({currency:r.currency,balance:r.granted_balance}))};}});
 }
 const poll=request.petWeb?setInterval(async()=>{try{const conf=await petApi('config');
   const has=Object.values(conf).some(v=>v?.pets?.some(p=>['web','both'].includes(p.display)));
   if(has&&!webVisible)send('web-surface','open');webVisible=has;}catch{}},3000):null;
 return {reply,restore:async()=>{const conf=await petApi('config');const pets=Object.values(conf).flatMap(v=>v?.pets||[]);
      let targets=pets.filter(p=>p.display==='web');
      if(!targets.length&&!pets.some(p=>['desktop','both'].includes(p.display)))targets=pets.filter(p=>p.display==='none').slice(0,1);
      for(const p of targets){const r=await petApi('pet-display',{id:p.id,display:'both'});if(r.ok!==true)throw Error('恢复桌面显示未成功');}
      send('log',targets.length?'原插件已确认恢复桌面及网页显示。':'桌宠已设为桌面显示，无需恢复。');},
   close:()=>{closed=true;clearInterval(poll);for(const p of waiting.values()){clearTimeout(p.timer);p.reject(Error('插件已停止'));}
      waiting.clear();server.closeAllConnections();server.close();}};
}
'''
