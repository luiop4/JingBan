"""Search public Bilibili metadata and read a browser address without changing UI."""
import base64
import html
import json
import re
import subprocess
import uuid

import requests


def search_videos(query: str, cancelled=lambda: False) -> list[dict]:
    query = query.strip()[:160]
    if not query:
        raise ValueError("请提供搜索关键词。")
    results = []
    try:
        if cancelled():
            return []
        with requests.Session() as session:
            session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"})
            response = session.get("https://api.bilibili.com/x/web-interface/search/type",
                params={"keyword": query, "search_type": "video", "page": 1}, timeout=(4, 8))
            response.raise_for_status()
            payload = response.json()
        if payload.get('code') == 0:
            for row in (payload.get('data') or {}).get('result', [])[:10]:
                bvid = row.get('bvid', '')
                if re.fullmatch(r'BV[a-zA-Z0-9]{10}', bvid):
                    results.append({'title': html.unescape(re.sub(r'<[^>]+>', '', row.get('title', '')))[:200],
                        'author': row.get('author', ''), 'duration': row.get('duration', ''),
                        'url': f'https://www.bilibili.com/video/{bvid}/', 'source': 'B站公开搜索',
                        'description': html.unescape(re.sub(r'<[^>]+>', '', row.get('description', '')))[:300]})
    except (requests.RequestException, ValueError, TypeError):
        pass
    if not results and not cancelled():
        from web_media import search_web
        seen = set()
        for row in search_web(query + ' site:bilibili.com', cancelled):
            match = re.search(r'/video/(BV[a-zA-Z0-9]{10})(?:[/?#]|$)', row['url'])
            if match and match[1] not in seen:
                seen.add(match[1])
                results.append({'title': row['title'], 'url': f'https://www.bilibili.com/video/{match[1]}/',
                    'description': row['snippet'], 'source': row['source'] + '网页索引',
                    'author': '', 'duration': ''})
    return results[:8]


def current_browser_videos() -> list[dict]:
    # UI Automation reads only known browser address fields. No clipboard, focus,
    # navigation, keyboard simulation or reading of arbitrary web form fields.
    script = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$windows = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
$results = @()
foreach ($window in $windows) {
  try {
    $process = [System.Diagnostics.Process]::GetProcessById($window.Current.ProcessId)
    if ($process.ProcessName -notin @('msedge','chrome','firefox','brave','vivaldi','opera')) { continue }
    if ($window.Current.IsOffscreen) { continue }
    $condition = [System.Windows.Automation.PropertyCondition]::new(
      [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
      [System.Windows.Automation.ControlType]::Edit)
    $edits = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
    foreach ($edit in $edits) {
      if ($edit.Current.Name -notmatch '地址|address|location|Search or enter') { continue }
      try {
        $value = $edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value
        if ($value -match '^(https?://)?((www|m)\.)?(bilibili\.com/video/|b23\.tv/)') {
          if ($value -notmatch '^https?://') { $value = 'https://' + $value }
          $results += @{url=$value; window=$window.Current.Name}
          break
        }
      } catch {}
    }
    if ($results.Count -ge 4) { break }
  } catch {}
}
ConvertTo-Json -InputObject @($results) -Compress
'''
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand",
         base64.b64encode(script.encode("utf-16-le")).decode("ascii")],
        capture_output=True, timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise ValueError("无法读取浏览器地址栏，请保持浏览器已打开且没有最小化。")
    values = json.loads(result.stdout.decode("utf-8-sig").strip() or "[]")
    return values if isinstance(values, list) else [values]
