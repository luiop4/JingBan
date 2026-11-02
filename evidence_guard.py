"""Per-turn tool receipts and conservative checks for operational claims.

This checks whether a capability was actually used; it cannot prove the truth
of every natural-language sentence or of arbitrary external command output.
"""
from datetime import datetime
import re
from urllib.parse import urlparse
from tool_context import source_url


HISTORY_TOOLS = {'read_self_state', 'read_companion_life', 'read_task_records', 'browse_history', 'search_history', 'search_images', 'search_events', 'search_long_memories', 'read_message', 'read_bilibili_visits'}


def operation_request(text):
    """A report that something stopped is not itself a new shutdown command."""
    if re.search(r'我看|我发现|怎么|为什么|为啥|好像|似乎|你说|你刚才|你不是|不是说|不动了|卡住|停在|暂停在', text):
        return bool(re.search(r'帮我|给我|请|修一下|恢复一下|继续播|接着播|重新播', text))
    return bool(re.search(r'关闭|关掉|再关|关一下|关了|打开|启动|停止|结束|杀掉|重启|删除|移动|复制|运行|执行|进程|服务|当前状态|再来|继续|^关[吧啊呀！!。]*$', text))


def conversational_failure(problem):
    # Keep verification details in tool records, not in the character's mouth.
    if re.search(r'播放|视频|漫游', problem):
        return '这边还没看清播放情况，我先不瞎说。'
    if re.search(r'图片|发图|绘图', problem):
        return '图片这次还没确认发出来，先别算发好了。'
    if re.search(r'联网|网页|查询|搜索', problem):
        return '这次还没查到能确认的结果，先不拿猜的糊弄你。'
    return '这次我还没确认好，先不说已经弄好了。'


def request_scope(text):
    historical = bool(re.search(r'之前|以前|上次|记得|回忆|刚才|刚刚|当时|那次', text))
    now = bool(re.search(r'现在|当前|正在|此刻|实时', text))
    # Discussing a feature or asking how it works is not a request to inspect it.
    explanation = bool(re.search(r'什么原理|怎么实现|如何实现|为什么|是什么|能不能|可不可以|支持.*吗|功能.*(?:怎么样|如何|不错)', text))
    inspect = bool(re.search(r'看看|看下|查看|检查|检测|查查|帮我查|给我查|读一下|读取|识别', text))
    live = bool(re.search(r'屏幕|桌面|窗口|进程|服务|CPU|显存|内存|浏览器|播放|在看', text, re.I)
                and re.search(r'看|检查|查|什么|啥|状态|占用|多少|运行', text)
                and (now or not historical) and (not explanation or now or inspect))
    live |= bool(re.search(r'(?:看看|看下).*(?:我现在|我正在|我在).*(?:干什么|做什么|忙什么)', text))
    web_lookup = bool(re.search(r'搜一下|搜索|搜搜|搜图|联网查|上网查', text)
                      or ('查一下' in text and not live))
    web_resource = bool(re.search(r'网页|网址|链接|网站|https?://', text) and inspect)
    fresh_info = bool(re.search(r'最新|新闻|天气', text))
    web = bool((web_lookup or web_resource or fresh_info) and not (historical and not now)
               and (not explanation or now or inspect))
    task = live or web or bool(re.search(r'帮我|给我|请|你.*(?:关|打开|运行|执行|删除|移动|复制)|发.*图|画.*图', text))
    return {'live': live, 'web': web, 'task': task}


class TurnEvidence:
    def __init__(self):
        self.receipts = []
        self.checks = []
        self.verified_files = []
        self.previous_receipts = []
        self.previous_checks = []

    def record(self, tool, args, result):
        failed = bool(result.get('error') or result.get('cancelled')
                      or result.get('stopped') and tool != 'stop_bilibili_session')
        if tool == 'run_computer_command':
            failed |= result.get('exit_code') != 0
        if tool == 'desktop_action':
            failed |= not bool(result.get('performed'))
        if tool == 'play_with_computer':
            failed |= not bool(result.get('performed'))
        if tool == 'chat_message':
            failed |= not bool(result.get('confirmed'))
        if tool == 'bilibili_interact':
            failed |= result.get('confirmed') is not True
        if tool.startswith('qq_'):
            failed |= not bool(result.get('confirmed'))
        if tool == 'qq_plan_activity':
            failed = not bool(result.get('queued'))
        if tool in {'read_app_settings', 'change_app_settings', 'query_api_balance'}:
            failed |= result.get('confirmed') is not True
        if tool == 'save_qq_sticker':
            failed |= not bool(result.get('saved'))
        if tool == 'send_sticker':
            failed |= not bool(result.get('sent'))
        scope = 'history' if tool in HISTORY_TOOLS else 'tool'
        if tool == 'chat_message':
            scope = 'conversation_message'
        if tool in {'search_web', 'search_web_images', 'search_videos'}:
            scope = 'search_summary'
        if tool in {'read_webpage', 'browse_webpage'}:
            scope = 'page_text'
        if tool in {'watch_video', 'review_recent_video'}:
            scope = 'sampled_video' if tool == 'watch_video' else 'historical_video'
        if tool in {'start_bilibili_session', 'get_bilibili_session', 'stop_bilibili_session', 'next_bilibili_video', 'bilibili_interact'}:
            scope = 'scheduled_task'
        if tool == 'qq_plan_activity':
            scope = 'scheduled_task'
        if tool in {'send_image', 'draw_picture', 'share_video_frame'}:
            scope = 'delivered_image'
            failed |= not bool(result.get('sent') or result.get('shared'))
        target = str(args.get('url') or args.get('local_path') or args.get('title') or args.get('keywords') or args.get('query') or args.get('reason') or '')
        if args.get('url'):
            parsed = urlparse(target)
            target = parsed.hostname or '网页'  # Do not store signed URL tokens.
        receipt = {'tool': tool, 'scope': scope, 'status': 'cancelled' if result.get('cancelled') else 'failed' if failed else 'success',
                   'observed_at': datetime.now().astimezone().isoformat(timespec='seconds'),
                   'target': target[:160]}
        # Small structured facts survive the turn; screenshots and raw command output do not.
        facts = {}
        if not failed:
            if tool == 'chat_message':
                facts = {'message_id': result.get('message_id'), 'image_shared': bool(result.get('image_shared')),
                         'waiting_for_reply': bool(result.get('waiting_for_reply'))}
            if tool in {'start_bilibili_session', 'get_bilibili_session', 'stop_bilibili_session', 'next_bilibili_video', 'bilibili_interact'}:
                session = result.get('session') or {}
                facts = {'task_id': result.get('task_id') or session.get('id'),
                         'task_status': result.get('status') or session.get('status'),
                         'new_visit_count': result.get('new_visit_count', 0)}
                if result.get('player'):
                    player = result['player']
                    facts['player'] = {key: player.get(key) for key in
                        ('url', 'title', 'paused', 'current_time', 'has_video', 'ended')}
                    facts['task_status'] = ('playing' if player.get('has_video') and not player.get('paused')
                        and float(player.get('current_time') or 0) > 0.3 else 'paused' if player.get('has_video') else 'preparing')
                if tool == 'bilibili_interact':
                    facts.update(action=result.get('action'), confirmed=True, comment_id=result.get('comment_id', ''),
                                 url=source_url(result.get('url') or args.get('url', '')),
                                 title=str(result.get('title', ''))[:200], backend=result.get('backend', 'browser_page'))
            elif tool in {'watch_video', 'review_recent_video', 'read_webpage', 'browse_webpage'}:
                facts = {'title': str(result.get('title', ''))[:200],
                         'url': source_url(result.get('url') or args.get('url', ''))}
                if tool == 'watch_video':
                    facts['origin'] = result.get('origin', {})
            elif tool == 'observe_desktop':
                facts = {'window_title': str(result.get('window_title', ''))[:240],
                         'visual': bool(result.get('visual'))}
            elif tool == 'desktop_action':
                facts = {'action': args.get('action'), 'performed': True,
                         'window_before': str(result.get('window_before', ''))[:240],
                         'window_after': str(result.get('window_after', ''))[:240],
                         'visual_after': bool(result.get('visual_after'))}
            elif tool == 'play_with_computer':
                facts = {key: result.get(key) for key in ('action', 'moves', 'verified_moves', 'completed', 'interrupted', 'restore_requested')}
            elif tool == 'read_message':
                facts = {'message_id': args.get('message_id')}
            elif tool in {'send_image', 'draw_picture', 'share_video_frame'}:
                facts = {'title': str(result.get('title') or args.get('title', ''))[:200],
                         'source_url': source_url(args.get('source_url', '')),
                         'frame_seconds': result.get('actual_time_seconds')}
            elif tool == 'run_computer_command':
                facts = {'exit_code': result.get('exit_code'),
                         'python': result.get('runtime', {}).get('python', ''),
                         'files': result.get('file_results', [])}
                self.verified_files.extend(row for row in facts['files'] if row.get('created_or_changed') and row.get('size', 0) > 0)
            elif tool.startswith('qq_'):
                facts = {'account': str(result.get('account') or result.get('user_id') or ''),
                         'tid': str(result.get('tid', '')), 'confirmed': True,
                         'duplicate_prevented': bool(result.get('duplicate_prevented'))}
                if tool == 'qq_reply_qzone_comment':
                    facts['comment_id'] = str(result.get('comment_id', ''))
            elif tool == 'change_app_settings':
                facts = {'changed': result.get('changed', {}), 'confirmed': True}
            elif tool == 'query_api_balance':
                facts = {'balance_infos': result.get('balance_infos', []), 'confirmed': True}
        if tool == 'bilibili_interact' and failed:
            facts = {'action': args.get('action'), 'confirmed': False,
                     'outcome_unknown': bool(result.get('outcome_unknown'))}
        if facts:
            receipt['facts'] = facts
        self.receipts.append(receipt)
        if tool == 'run_computer_command' and not failed:
            self.checks.append(str(args.get('command', '')))
        return receipt

    def has(self, tools, include_previous=False):
        rows = self.receipts + self.previous_receipts if include_previous else self.receipts
        return any(r['tool'] in tools and r['status'] == 'success' for r in rows)

    def violation(self, text, image_count=0, visual_input=False):
        # Reported speech, instructions and explicit uncertainty are not execution claims.
        # Inspect sentences separately so one disclaimer cannot excuse another claim.
        sentences = re.split(r'[。！!？?；;\n]', text)
        for sentence in sentences:
            browse_promise = re.search(r'(?:本鲸|我).{0,12}(?:自己逛去|去逛|去刷|开刷|挑.{0,5}新的|开始.{0,4}漫游)|(?:正在|已经|已开始).{0,6}(?:刷B站|刷b站|漫游)', sentence)
            if browse_promise and not re.search(r'没|未|不能|无法|不会|不再|如果|假如|你说|你让我', sentence):
                active = any(row.get('status') == 'success' and row.get('scope') == 'scheduled_task'
                             and row.get('facts', {}).get('task_status') in {'opening', 'playing', 'summarizing'}
                             for row in self.receipts)
                if not active and not self.has({'start_bilibili_session', 'next_bilibili_video'}):
                    return '没有本轮实际安排漫游的回执，不能只口头说自己去刷、去逛或去挑新视频。读取旧札记不会启动任务。'
                if re.search(r'(?:正在|已经|已开始).{0,6}(?:刷B站|刷b站|漫游)', sentence):
                    playing = any(row.get('status') == 'success' and row.get('scope') == 'scheduled_task'
                                  and row.get('facts', {}).get('task_status') == 'playing' for row in self.receipts)
                    if not playing:
                        return '目前回执未确认正在播放；可说已安排或正在准备，不能把排队说成已开刷。'
            if re.search(r'还没|没有|尚未|不能确认|无法确认|没能|未能|失败|不确定|未核实|未执行|未发送|未读取|未查到|如果|假如|你说|你之前|你让我|你要求|你可以|请你', sentence):
                continue
            past = bool(re.search(r'刚才|刚刚|上次|那次|之前|当时', sentence)
                        and not re.search(r'现在|当前|这次|本轮', sentence))
            checks = self.previous_checks if past else self.checks
            qq_tools = {'qq_publish_qzone', 'qq_set_profile', 'qq_set_avatar', 'qq_set_status', 'qq_reply_qzone_comment'}
            qq_sentence = bool(re.search(r'QQ|qq|说说|空间动态', sentence)
                               or self.has(qq_tools, past) and re.search(r'昵称|头像|签名|状态', sentence))
            qq_completion = bool(re.search(r'已(?:经)?|改好了|改成了|换好了|换成了|设置好了|发布了|发好了|发出去了|发布成功|更新了|回复了|回了|回复好了', sentence))
            qq_action = None
            bili_write = any(row.get('tool') == 'bilibili_interact' and
                row.get('facts', {}).get('action') in {'comment', 'like', 'unlike'} for row in
                (self.previous_receipts if past else self.receipts))
            if (bili_write or re.search(r'B站|bilibili', sentence, re.I)) and re.search(r'评论|点赞', sentence):
                published = re.search(r'发出去了|发出去|发了|发布了|发布成功|已(?:经)?(?:发出|发了|发布|评论|点赞)|点赞了|评论发好了|取消了.{0,4}赞|赞.{0,4}取消了', sentence)
                if published:
                    action = 'unlike' if re.search(r'取消.{0,4}赞|赞.{0,4}取消', sentence) else 'like' if '点赞' in sentence else 'comment'
                    if not any(row.get('tool') == 'bilibili_interact' and row.get('status') == 'success'
                            and row.get('facts', {}).get('action') == action for row in
                            (self.previous_receipts if past else self.receipts)):
                        return '没有该项B站互动的成功结果，不能把提交结果不明说成已经发布。'
            sticker_sentence = bool(re.search(r'表情|贴纸', sentence))
            if sticker_sentence and re.search(r'已.{0,4}(?:收藏|保存)|收藏了|收藏好了|保存好了', sentence):
                if not self.has({'save_qq_sticker'}, past):
                    return '没有本轮收藏表情的成功回执，不能声称已收藏。'
            if qq_sentence and qq_completion:
                if re.search(r'评论', sentence) and re.search(r'回复|回了', sentence):
                    qq_action = 'qq_reply_qzone_comment'
                elif re.search(r'说说|动态', sentence):
                    qq_action = 'qq_publish_qzone'
                elif re.search(r'头像', sentence):
                    qq_action = 'qq_set_avatar'
                elif re.search(r'昵称|签名|资料', sentence):
                    qq_action = 'qq_set_profile'
                elif re.search(r'状态|隐身|忙碌|离开|在线', sentence):
                    qq_action = 'qq_set_status'
                if qq_action and not self.has({qq_action}, past):
                    return '没有该项 QQ 操作的成功回执，不能宣称发布或修改完成；结果不明不能重复执行。'
            if re.search(r'(?:我|本鲸|人家).{0,8}(?:搜到|查到|搜索了|查过)|(?:已|已经).{0,4}(?:搜索|联网查)', sentence):
                extra_queries = {'query_api_balance'} if re.search(r'余额|赠金|充值|用量', sentence) else {'read_app_settings'} if '设置' in sentence else set()
                if not self.has({'search_web', 'search_web_images', 'search_videos'} | HISTORY_TOOLS | extra_queries, past):
                    return '没有本轮查询回执，不能宣称已搜索或查过。'
            if re.search(r'(?:联网|网上|网络).{0,6}(?:查到|搜到|查过)|(?:已|已经).{0,3}联网', sentence):
                if not self.has({'search_web', 'search_web_images', 'search_videos', 'read_webpage', 'browse_webpage'}, past):
                    return '没有本轮联网结果，不能把历史检索说成网络查询。'
            if re.search(r'(?:我|本鲸).{0,8}(?:读完|看完|读过|阅读了).{0,8}(?:网页|文章|链接)|(?:网页|文章).{0,6}(?:看完了|读完了)', sentence):
                if not self.has({'read_webpage', 'browse_webpage'}, past):
                    return '只有搜索摘要或历史内容，不能宣称读过网页正文。'
            if re.search(r'(?:屏幕|桌面).{0,8}(?:显示|是|有)|(?:我|本鲸).{0,6}(?:看到了|看见了).{0,8}(?:屏幕|桌面)', sentence):
                conceptual = re.search(r'(?:屏幕截图|屏幕观察|截屏).{0,10}(?:工具|方式|路径|功能|方法)', sentence)
                if not visual_input and not conceptual:
                    return '没有本轮屏幕观察，不能描述当前桌面画面。'
            if re.search(r'当前窗口.{0,8}(?:显示|是|有)', sentence) and not self.has({'observe_desktop'}):
                return '没有本轮窗口读取，不能确认当前窗口。'
            if re.search(r'(?:我|本鲸).{0,8}(?:发出|发送|贴出|画好|画完).{0,8}了|(?:已|已经).{0,6}(?:发图|发送图片|画好)', sentence):
                flow_image = any(row.get('tool') == 'chat_message' and row.get('status') == 'success'
                                 and row.get('facts', {}).get('image_shared')
                                 for row in (self.previous_receipts if past else self.receipts))
                if not image_count and not flow_image and not (qq_sentence and self.has({'qq_publish_qzone', 'qq_set_avatar'}, past)) and not (sticker_sentence and self.has({'send_sticker'}, past)):
                    return '没有本轮图片卡片，不能宣称发图或绘图完成。'
            command_claims = {
                r'已(?:经)?(?:删除|删掉)|删除了|删掉了|清空了': r'Remove-Item|\bdel\b|\brm\b|unlink|rmtree',
                r'已(?:经)?(?:关闭|停止|结束)|关掉了|关闭了|停止了': r'Stop-Process|Stop-Service|taskkill|\.kill\(|\.terminate\(',
                r'已(?:经)?(?:打开|启动)|打开了|启动了': r'Start-Process|Invoke-Item|\.Popen\(|os\.startfile|start\s',
                r'已(?:经)?复制|复制好了|复制了': r'Copy-Item|copyfile|copytree|shutil\.copy|\bcopy\b',
                r'已(?:经)?移动|移动了': r'Move-Item|shutil\.move|\bmove\b',
                r'已(?:经)?(?:修改|写入|保存文件)|改好了|写好了|保存好了': r'Set-Content|Add-Content|Out-File|write_text|write_bytes|\.write\(',
            }
            for claim, command in command_claims.items():
                if re.search(claim, sentence) and not any(re.search(command, check, re.I) for check in checks):
                    rows = self.previous_receipts if past else self.receipts
                    if re.search(r'视频|播放|播放器|漫游|B站|bilibili', sentence, re.I):
                        player_rows = [r for r in rows if r.get('status') == 'success' and
                            r.get('tool') in {'bilibili_interact', 'get_bilibili_session', 'stop_bilibili_session'}]
                        players = [r.get('facts', {}).get('player') for r in player_rows if r.get('facts', {}).get('player')]
                        if re.search(r'停止|结束|关闭|关掉', sentence):
                            if not re.search(r'窗口|标签|浏览器|关闭|关掉', sentence) and any(
                                    p.get('paused') or p.get('ended') for p in players):
                                continue
                        elif re.search(r'打开|启动', sentence) and any(p.get('has_video') for p in players):
                            continue
                        if any(r.get('facts', {}).get('action') == 'open' for r in player_rows) and re.search(r'打开|启动', sentence):
                            continue
                        if self.has({'stop_bilibili_session'}, past) and re.search(r'停止|结束', sentence) and '漫游' in sentence:
                            continue
                    if any(row['tool'] == 'desktop_action' and row['status'] == 'success'
                           and row.get('facts', {}).get('visual_after') for row in rows):
                        continue  # A real post-action frame is available for UI verification.
                    if self.has({'play_with_computer'}, past) and re.search(r'鼠标|窗口', sentence) and not re.search(r'删除|关闭|写入|复制|文件', sentence):
                        continue
                    if qq_action and self.has({qq_action}, past):
                        continue
                    if re.search(r'设置|思考|语速|通知|模式|偏好|间隔|语音回复|跳看', sentence) and self.has({'change_app_settings'}, past):
                        continue
                    if sticker_sentence and self.has({'save_qq_sticker'}, past) and re.search(r'收藏|保存', sentence):
                        continue
                    if not past and self.verified_files and re.search(r'保存好了|写好了', sentence):
                        continue
                    return '本轮没有对应操作的成功命令回执，不能宣称该操作完成。'
            if re.search(r'下载(?:好|完|成功|下来了|到了)|已(?:经)?下载|保存了.{0,10}(?:音频|歌曲|视频)', sentence):
                download = any(re.search(r'(?:-m\s+yt_dlp|\byt-dlp(?:\.exe)?)\s+(?!.*--version)|'
                                         r'Invoke-WebRequest|\bcurl\b|\bwget\b|DownloadFile|urlretrieve|extract_info\(', check, re.I)
                               for check in checks)
                verified = ([file for receipt in self.previous_receipts if receipt.get('status') == 'success'
                             for file in receipt.get('facts', {}).get('files', [])
                             if file.get('created_or_changed') and file.get('size', 0) > 0] if past else self.verified_files)
                if not download or not verified:
                    return '下载完成需要实际下载命令和已生成文件的检查；安装组件或查看版本不能证明下载完成。请在下载命令中填写expected_files核对输出。'
            if re.search(r'确认.{0,8}(?:运行中|已关闭|已停止)|(?:当前|现在).{0,12}(?:进程|服务).{0,8}(?:运行|停止|关闭)', sentence):
                if not any(re.search(r'Get-Process|Get-Service|Get-CimInstance|tasklist|psutil', check, re.I) for check in checks):
                    return '没有本轮进程或服务状态检查，不能确认当前状态。'
            if re.search(r'(?:CPU|显存|内存).{0,8}(?:占用|使用率).{0,8}(?:\d|百分之)', sentence, re.I):
                if not any(re.search(r'Get-Counter|Get-CimInstance|nvidia-smi|psutil|Get-Process', check, re.I) for check in checks):
                    return '没有本轮系统指标读取，不能报告当前资源占用。'
        return None

    def prompt(self):
        import json
        return ('\n本轮实际工具回执（程序生成，不是回复模板）：' + json.dumps(self.receipts[-20:], ensure_ascii=False) +
                '\nsuccess只证明该工具已返回。搜索摘要不是网页正文，缓存不是实时观察，'
                '命令退出码不证明目标程序/文件已达到预期；有必要再读取目标状态核实。'
                'desktop_action 仅证明输入已提交；visual_after 仅说明提供了后续真实截图，必须从图中核实目标是否达到。'
                '旧回执仅属于旧时间，不能据此描述当前状态。没有证据时保留不确定性，不伪造完成。')
