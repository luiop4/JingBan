"""Rank archive evidence separately from later questions about that evidence."""
import re
from history_intent import archive_question


def recall_request(text):
    return archive_question(text)['explicit'] and bool(re.search(
        r'吗|么|什么|啥|哪|记得|查|找|回忆|翻|[?？]', text))


def search_terms(text):
    cleaned = re.sub(r'你还记得吗|你还记得|还记得|记不记得|之前|以前|上次|我说过|你说过|'
                     r'我提过|我之前|你之前|你当时|还记|回忆|查询|查找|找一下|帮我|给我|'
                     r'什么|啥|怎么样|当时|说过|提过|聊过|发过|说的|记得|吗|呢|的', ' ', text.lower())
    return [word for word in re.findall(r'\w+', cleaned) if word not in {'我', '你', '她', '他', '有', '是', '和', '给', '了'}][:12]


def rank_history(rows, query, quote_links=(), exclude_ids=(), minimum=0, assistant_cutoff=0):
    words = search_terms(query)
    fragments = {w[i:i+2] for w in words if re.search(r'[\u4e00-\u9fff]', w) for i in range(len(w)-1)}
    by_id = {row['id']: row for row in rows}
    # Classify in the original conversation order, not global numeric adjacency.
    kinds = {}
    previous_user_recalls = {}
    for row in sorted(rows, key=lambda r: r['id']):
        conversation = row['conversation_key']
        previous_user_recall = previous_user_recalls.get(conversation, False)
        if row['role'] == 'user':
            previous_user_recall = recall_request(row['content'])
            previous_user_recalls[conversation] = previous_user_recall
            kinds[row['id']] = 'recall_request' if previous_user_recall else 'original_statement'
        else:
            kinds[row['id']] = 'recall_reply' if previous_user_recall else 'original_reply'
    scores = {}
    for row in rows:
        title = row['peer_name'] if row['source'] == 'dsh' else ''
        haystack = (row['content'] + ' ' + row['files'] + ' ' + title).lower()
        raw = sum(8 for word in words if word in haystack) + sum(1 for word in fragments if word in haystack)
        if words and not raw:
            continue
        if raw < minimum:
            continue
        kind = kinds[row['id']]
        scores[row['id']] = (raw, raw * (0.15 if kind.startswith('recall_') else 1.0))
    provenance = {}
    # A later recollection's explicit quote can identify the older source even if
    # that source uses different words. Never infer provenance from proximity alone.
    links = {}
    for source, target in quote_links:
        if source in by_id and target in by_id and target < source:
            links.setdefault(source, []).append(target)
    for source in list(scores):
        if not kinds[source].startswith('recall_'):
            continue
        frontier = [(source, 0)]
        visited = {source}
        while frontier:
            node, depth = frontier.pop()
            if depth >= 4:
                continue
            for target in links.get(node, []):
                if target in visited:
                    continue
                visited.add(target)
                if not kinds[target].startswith('recall_'):
                    raw = scores[source][0]
                    old_raw, old_score = scores.get(target, (0, 0))
                    scores[target] = (max(raw, old_raw), max(raw, old_score))
                    provenance.setdefault(target, []).append(source)
                else:
                    frontier.append((target, depth+1))
    results = []
    for message_id, (raw, score) in scores.items():
        row = by_id[message_id]
        if message_id in exclude_ids or (row['role'] == 'assistant' and message_id <= assistant_cutoff):
            continue
        results.append((score, message_id, row, kinds[message_id], provenance.get(message_id, [])))
    return sorted(results, key=lambda item: (item[0], item[1]), reverse=True)
