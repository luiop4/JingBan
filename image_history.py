"""Find actual uploads, never substitute later recollections for image sources."""
import re


def is_image_recall(text, tool_followup=False):
    if tool_followup:
        return False
    return bool(re.search(r'图片|照片|截图|那张图|这张图|张图|原图|发的图', text)
                and re.search(r'之前|以前|最早|第一次|最初|上次|原来|记得|回忆|找|查|发过|发的|那张', text))


def image_terms(text):
    text = re.sub(r'你还记得吗|还记得|记不记得|之前|以前|最早|第一次|最初|上次|原来|回忆|'
                  r'图片|照片|截图|那张图|这张图|原图|张图|一张|那张|这张|'
                  r'发给你|给你发|我发过|我发的|我之前|发过|发的|帮我|给我|你觉得|评价|'
                  r'什么|啥|怎么样|那个|这个|当时|记得|查询|查找|找一下|看看|重新|一下|能不能|吗|呢|的',
                  ' ', text.lower())
    return [word for word in re.findall(r'\w+', text) if word not in {'我', '你', '她', '他', '有', '是', '和', '给', '了'}][:12]


def search_image_origins(database, conversation, query, exclude_ids=(), limit=6):
    words = image_terms(query)
    fragments = {w[i:i+2] for w in words if re.search(r'[\u4e00-\u9fff]', w)
                 for i in range(len(w)-1)}
    scope, keys = database.archive_scope(conversation, 'm.conversation_key')
    with database._connect() as con:
        rows = con.execute('''SELECT m.id,m.role,m.content,m.created_at,m.conversation_key,m.source,
            group_concat(a.file_name, ' ') AS files
            FROM messages m JOIN message_attachments a ON a.message_id=m.id AND a.kind='image'
            WHERE '''+scope+''' AND m.role='user' GROUP BY m.id ORDER BY m.id''', keys).fetchall()
        ranked = []
        for row in rows:
            if row['id'] in exclude_ids:
                continue
            # Only replies in the original upload's turn can supply descriptive clues.
            replies = con.execute('''SELECT content FROM messages WHERE conversation_key=? AND role='assistant'
                AND id>? AND id<COALESCE((SELECT min(id) FROM messages
                WHERE conversation_key=? AND role='user' AND id>?),9223372036854775807)
                ORDER BY id LIMIT 2''', (row['conversation_key'], row['id'], row['conversation_key'], row['id'])).fetchall()
            upload = (row['content'] + ' ' + (row['files'] or '')).lower()
            description = ' '.join(r['content'][:1400] for r in replies).lower()
            score = sum(12 for w in words if w in upload) + sum(6 for w in words if w in description)
            score += sum(2 for w in fragments if w in upload) + sum(1 for w in fragments if w in description)
            ranked.append((score, row, description))
    matching = [item for item in ranked if item[0] > 0] if words else []
    selected = matching or ranked
    oldest = bool(re.search(r'最早|最初|第一次', query))
    # Empty searches are explicitly uncertain browse results, not a claim of a match.
    selected.sort(key=lambda item: (item[1]['created_at'], item[1]['id']), reverse=not oldest)
    selected.sort(key=lambda item: -item[0])
    return {'matches': [dict(row) | {'has_image': 1, 'source_kind': 'original_image_upload',
            'content': row['content'][:500], 'original_reply_clue': description[:700],
            'match_score': score} for score, row, description in selected[:limit]],
            'needs_disambiguation': not bool(matching) or (len(selected) > 1 and selected[0][0] == selected[1][0]),
            'note': '这里只返回当前会话真正上传图片的用户消息，包含隐藏记录。原回复描述只作检索线索，'
                    '不代表本轮看过图片；不包含后来的回忆请求或转述。匹配不明确时让用户确认候选，'
                    '不能把最新候选直接当成所指图片。引用原图消息ID。可用read_message回读原图。'}
