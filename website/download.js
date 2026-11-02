const packageLink=document.querySelector('#download-package');
let packageVersion=null;
function comparePackageVersion(){
  const update=window.JingbanVersion?.current?.updateVersion;
  let note='';
  if(update&&packageVersion){
    const relation=window.JingbanVersion.compare(packageVersion,update);
    if(relation>0)note='完整安装包 v'+packageVersion+' 比联网更新通道 v'+update+' 更新，两条通道独立发布。首次安装或升级可使用这份完整安装包。';
    if(relation<0)note='完整安装包为 v'+packageVersion+'，联网更新通道已到 v'+update+'。安装后可通过启动器检查更新。';
  }
  document.querySelector('#package-version-note').textContent=note;
}
async function loadRelease(){
  try{
    const response=await fetch('release.json',{cache:'no-store'});
    if(!response.ok)throw Error('Release unavailable');
    const r=await response.json();
    if(typeof r.version!=='string'||!/^\d+(?:\.\d+){1,3}$/.test(r.version)||typeof r.filename!=='string'||!r.filename||!Number.isSafeInteger(r.bytes)||r.bytes<=0||typeof r.sha256!=='string'||!/^[a-f0-9]{64}$/i.test(r.sha256))throw Error('Invalid package metadata');
    packageVersion=r.version;document.querySelector('#release-version').textContent='v'+r.version;
    document.querySelector('#release-size').textContent=Math.round(r.bytes/1024/1024)+' MiB';
    document.querySelector('#release-filename').textContent=r.filename;document.querySelector('#release-sha').textContent=r.sha256;
    const installer=/\.exe$/i.test(r.filename);
    document.querySelector('#release-format').textContent=installer?'EXE':'ZIP';
    document.querySelector('.release-subtitle').textContent=installer?'完整安装版 · 中文安装向导':'纯净便携版 · 解压后启动';comparePackageVersion();
    if(r.published===true&&typeof r.url==='string'&&r.url){
      const url=new URL(r.url,location.href);if(!['https:','http:'].includes(url.protocol))throw Error('Invalid URL');
      packageLink.href=url.href;packageLink.removeAttribute('tabindex');packageLink.setAttribute('aria-disabled','false');
      document.querySelector('#download-label').textContent=installer?'下载 Windows 安装包':'下载 Windows 便携版';
      document.querySelector('#release-status').textContent='完整纯净发行版已就绪';
      document.querySelector('#release-note').textContent=installer?'下载后运行 EXE，跟随中文安装向导完成安装。':'下载完整 ZIP，解压后运行鲸伴。';
      document.querySelector('.availability-dot').style.background='#8bd6bd';
      document.querySelector('.integrity-card>small').textContent='请核对上方文件名及 SHA-256。';
    }else{
      document.querySelector('#release-status').textContent='新版安装包准备中';document.querySelector('#release-note').textContent='正在准备公开下载，发布后此处将启用下载按钮。';
    }
  }catch{
    document.querySelector('#release-status').textContent='暂时无法读取安装包信息';document.querySelector('#release-note').textContent='请稍后刷新页面，上手指南仍可保存。';
  }
}
document.querySelector('#copy-sha').addEventListener('click',async()=>{
  const result=document.querySelector('#copy-result');
  try{await navigator.clipboard.writeText(document.querySelector('#release-sha').textContent);result.textContent='已复制';}
  catch{result.textContent='请选中上方校验值复制';}
});
document.addEventListener('jingban:version',comparePackageVersion);loadRelease();
