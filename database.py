from __future__ import annotations

import sqlite3
import json
import hashlib
import re
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path


class ChatDatabase:
    """SQLite storage for the single visible timeline and approved memories."""

    def __init__(self, database_path: Path):
        self._owner_peer = ''
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()
        from standard_memory import StandardMemory
        self.standard_memory = StandardMemory(self)
        self.standard_memory.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_key TEXT NOT NULL,
                    source TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    peer_id TEXT NOT NULL DEFAULT '',
                    peer_name TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_timeline
                    ON messages(created_at, id);
                CREATE INDEX IF NOT EXISTS idx_messages_context
                    ON messages(conversation_key, id);

                CREATE TABLE IF NOT EXISTS message_extras (
                    message_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    target TEXT NOT NULL,
                    PRIMARY KEY (message_id, kind, target)
                );

                CREATE TABLE IF NOT EXISTS hidden_messages (
                    message_id INTEGER PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS dsh_import_items (
                    session_key TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    PRIMARY KEY(session_key, item_key)
                );
                CREATE INDEX IF NOT EXISTS idx_dsh_import_message ON dsh_import_items(message_id);
                CREATE TABLE IF NOT EXISTS conversation_video (
                    conversation_key TEXT PRIMARY KEY,
                    message_id INTEGER NOT NULL,
                    manifest TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS command_traces (
                    operation_id TEXT PRIMARY KEY,
                    message_id INTEGER NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_command_traces_message ON command_traces(message_id);

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    source TEXT NOT NULL DEFAULT 'manual',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memory_sources (
                    memory_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    PRIMARY KEY (memory_id, message_id)
                );
                CREATE INDEX IF NOT EXISTS idx_memory_sources_message
                    ON memory_sources(message_id);

                CREATE TABLE IF NOT EXISTS audio_batches (
                    batch_id TEXT PRIMARY KEY,
                    message_id INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_audio_batches_message
                    ON audio_batches(message_id);

                CREATE TABLE IF NOT EXISTS audio_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audio_files_batch
                    ON audio_files(batch_id, id);

                CREATE TABLE IF NOT EXISTS message_attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    file_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    mime_type TEXT NOT NULL DEFAULT '',
                    local_path TEXT NOT NULL DEFAULT '',
                    extracted_text TEXT NOT NULL DEFAULT '',
                    size_bytes INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_attachments_message
                    ON message_attachments(message_id, id);

                CREATE TABLE IF NOT EXISTS api_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model TEXT NOT NULL DEFAULT '',
                    request_kind TEXT NOT NULL DEFAULT 'chat',
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    cached_tokens INTEGER NOT NULL DEFAULT 0,
                    request_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_api_usage_created
                    ON api_usage(created_at, id);

                CREATE TABLE IF NOT EXISTS context_settings (
                    conversation_key TEXT PRIMARY KEY,
                    style_anchor TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS owner_notifications (
                    message_id INTEGER NOT NULL,
                    peer_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(message_id, peer_id)
                );
                CREATE TABLE IF NOT EXISTS qq_proactive (
                    id TEXT PRIMARY KEY,
                    peer_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_qq_proactive_peer ON qq_proactive(peer_id, at);
                CREATE TABLE IF NOT EXISTS interaction_waits (
                    conversation_key TEXT PRIMARY KEY,
                    message_id INTEGER NOT NULL,
                    question TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    next_step TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agency_state (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agency_journal (
                    id TEXT PRIMARY KEY,
                    owner_pid INTEGER NOT NULL DEFAULT 0,
                    owner_token TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    intent TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    receipts TEXT NOT NULL DEFAULT '[]',
                    message_id INTEGER
                );
                """
            )
            columns = {row[1] for row in connection.execute('PRAGMA table_info(agency_journal)')}
            for name, declaration in (('owner_pid', 'INTEGER NOT NULL DEFAULT 0'),
                                      ('owner_token', "TEXT NOT NULL DEFAULT ''")):
                if name not in columns:
                    connection.execute(f'ALTER TABLE agency_journal ADD COLUMN {name} {declaration}')
            connection.execute("UPDATE message_extras SET target='unknown' WHERE kind='qq_delivery' AND target='pending' "
                               "AND EXISTS(SELECT 1 FROM message_extras f WHERE f.message_id=message_extras.message_id AND f.kind='chat_flow')")
            from companion_life import SCHEMA
            connection.executescript(SCHEMA)

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def clear_all_conversation_data(self) -> dict:
        """Clear conversation state atomically; retain schema and user preferences."""
        tables = (
            'message_extras', 'hidden_messages', 'conversation_video', 'command_traces',
            'memory_sources', 'audio_files', 'audio_batches', 'message_attachments',
            'event_sources', 'event_processed', 'event_revisions', 'event_memories',
            'event_search', 'memories', 'api_usage', 'context_settings', 'owner_notifications', 'qq_proactive',
            'agency_state', 'agency_journal', 'interaction_waits', 'dsh_import_items', 'companion_meta', 'companion_events',
            'companion_intentions', 'companion_decisions', 'messages',
        )
        with closing(self._connect()) as connection, connection:
            connection.execute('BEGIN IMMEDIATE')
            existing = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            counts = {name: connection.execute(f'SELECT count(*) FROM {name}').fetchone()[0]
                      for name in ('messages', 'memories', 'event_memories')}
            for table in tables:
                if table in existing:
                    connection.execute(f'DELETE FROM {table}')
            connection.execute("DELETE FROM memory_scheme_settings WHERE key IN ('auto_after_id','last_success','last_error')")
            connection.execute("INSERT INTO memory_scheme_settings VALUES ('auto_after_id','0')")
            # Keep AUTOINCREMENT counters: an obsolete message ID must never be reused.
        return counts

    def save_message(
        self,
        conversation_key: str,
        source: str,
        role: str,
        content: str,
        peer_id: str = "",
        peer_name: str = "",
        created_at: str | None = None,
    ) -> int:
        created_at = created_at or self._now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages
                    (conversation_key, source, role, content, peer_id, peer_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (conversation_key, source, role, content, str(peer_id), peer_name, created_at),
            )
            return int(cursor.lastrowid)

    def save_activity_record(self, episode, summary, receipts, operation_ids):
        """Write internal audit and its visibility atomically."""
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "INSERT INTO messages(conversation_key,source,role,content,created_at) VALUES('local','local','assistant',?,?)",
                ('自主活动记录：'+str(summary or '本轮未发送聊天消息。')[:1600], self._now()))
            message_id = int(cursor.lastrowid)
            connection.execute('INSERT INTO hidden_messages VALUES(?)', (message_id,))
            connection.executemany('INSERT INTO message_extras VALUES(?,?,?)', [
                (message_id, 'proactive', 'local'), (message_id, 'internal_activity', episode),
                (message_id, 'tool_receipts', json.dumps(receipts, ensure_ascii=False))])
            connection.executemany('UPDATE command_traces SET message_id=? WHERE operation_id=?',
                                   [(message_id, identity) for identity in operation_ids])
        return message_id

    def reset_message_for_regeneration(self, message_id: int) -> tuple[bool, list[str]]:
        """Temporarily blank a reply while preserving its saved extras and audio."""
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM messages WHERE id=? AND role='assistant' AND source='local'",
                (message_id,),
            ).fetchone()
            if exists is None:
                return False, []
            self._clear_interaction_wait(connection, message_id)
            connection.execute("UPDATE messages SET content='' WHERE id=?", (message_id,))
            connection.execute("UPDATE owner_notifications SET status='cancelled' WHERE message_id=? AND status='queued'", (message_id,))
            return True, []

    def clear_regenerated_reply_artifacts(self, message_id: int) -> list[str]:
        with self._connect() as connection:
            paths = [row[0] for row in connection.execute(
                "SELECT f.file_path FROM audio_files f JOIN audio_batches b ON b.batch_id=f.batch_id WHERE b.message_id=?",
                (message_id,),
            )]
            connection.execute("DELETE FROM audio_files WHERE batch_id IN (SELECT batch_id FROM audio_batches WHERE message_id=?)", (message_id,))
            connection.execute("DELETE FROM audio_batches WHERE message_id=?", (message_id,))
            connection.execute("DELETE FROM message_extras WHERE message_id=?", (message_id,))
            connection.execute("DELETE FROM command_traces WHERE message_id=?", (message_id,))
            return [str(path) for path in paths]

    def update_message_content(self, message_id: int, content: str) -> bool:
        with self._connect() as connection:
            return connection.execute(
                "UPDATE messages SET content=? WHERE id=? AND role='assistant' AND source='local'",
                (content, message_id),
            ).rowcount > 0

    def get_timeline(self, limit: int = 300, mode: str = 'normal') -> list[dict]:
        with self._connect() as connection:
            lane = "conversation_key='local:work'" if mode == 'work' else "conversation_key<>'local:work'"
            rows = connection.execute(
                "SELECT * FROM messages WHERE " + lane + " AND id NOT IN (SELECT message_id FROM hidden_messages) ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def get_message(self, message_id: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute('SELECT * FROM messages WHERE id=?', (message_id,)).fetchone()
        return dict(row) if row else None

    def save_command_trace(self, message_id: int, progress: dict) -> None:
        with self._connect() as connection:
            row = connection.execute('SELECT payload FROM command_traces WHERE operation_id=?', (progress['id'],)).fetchone()
            payload = json.loads(row['payload']) if row else {}
            payload.update(progress)
            payload['recorded_at'] = self._now()
            connection.execute('INSERT INTO command_traces VALUES (?, ?, ?) ON CONFLICT(operation_id) DO UPDATE SET payload=excluded.payload',
                               (progress['id'], message_id, json.dumps(payload, ensure_ascii=False)))

    def bind_command_traces(self, message_id: int, operation_ids: list[str]) -> None:
        with self._connect() as connection:
            connection.executemany('UPDATE command_traces SET message_id=? WHERE operation_id=?',
                                   [(message_id, value) for value in operation_ids])

    def command_traces_for_message(self, message_id: int) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute('SELECT payload FROM command_traces WHERE message_id=? ORDER BY rowid', (message_id,)).fetchall()
        results = []
        for row in rows:
            payload = json.loads(row['payload'])
            if not payload.get('finished'):
                payload['phase'] = '未记录最终结果'
            results.append(payload)
        return results

    @staticmethod
    def _history_filter(filters: dict) -> tuple[str, list]:
        clauses, values = ['1=1'], []
        if filters.get('keyword'):
            clauses.append("(instr(lower(m.content), lower(?)) > 0 OR (m.source='dsh' AND instr(lower(m.peer_name),lower(?))>0) OR EXISTS (SELECT 1 FROM message_attachments a WHERE a.message_id=m.id AND instr(lower(a.file_name), lower(?)) > 0))")
            values.extend([filters['keyword']] * 3)
        if filters.get('start'):
            clauses.append('substr(m.created_at,1,10) >= ?')
            values.append(filters['start'])
        if filters.get('end'):
            clauses.append('substr(m.created_at,1,10) <= ?')
            values.append(filters['end'])
        state = filters.get('state', 'visible')
        if state in ('visible', 'hidden'):
            clauses.append('m.id ' + ('NOT IN' if state == 'visible' else 'IN') + ' (SELECT message_id FROM hidden_messages)')
        return ' AND '.join(clauses), values

    def history_page(self, filters: dict, page: int = 0) -> tuple[list[dict], int]:
        where, values = self._history_filter(filters)
        with self._connect() as connection:
            count = connection.execute('SELECT count(*) FROM messages m WHERE ' + where, values).fetchone()[0]
            rows = connection.execute('SELECT m.*, EXISTS(SELECT 1 FROM hidden_messages h WHERE h.message_id=m.id) AS hidden FROM messages m WHERE '
                                      + where + ' ORDER BY m.id DESC LIMIT 100 OFFSET ?', [*values, max(0, page)*100]).fetchall()
        return [dict(row) for row in rows], count

    def set_history_hidden(self, hidden: bool, ids: list[int] | None = None, filters: dict | None = None) -> int:
        """只修改显示状态，不触碰消息、附件、引用和记忆。"""
        with self._connect() as connection:
            if ids is not None:
                changed = 0
                for message_id in set(ids):
                    sql = ('INSERT OR IGNORE INTO hidden_messages SELECT id FROM messages WHERE id=?' if hidden
                           else 'DELETE FROM hidden_messages WHERE message_id=?')
                    changed += connection.execute(sql, (message_id,)).rowcount
                return changed
            where, values = self._history_filter(filters or {})
            query = 'SELECT m.id FROM messages m WHERE ' + where
            sql = ('INSERT OR IGNORE INTO hidden_messages ' + query if hidden else
                   'DELETE FROM hidden_messages WHERE message_id IN (' + query + ')')
            return connection.execute(sql, values).rowcount

    def history_ids(self, filters: dict) -> list[int]:
        where, values = self._history_filter(filters)
        with self._connect() as connection:
            return [row[0] for row in connection.execute(
                'SELECT m.id FROM messages m WHERE ' + where, values).fetchall()]

    def _clear_interaction_wait(self, connection, message_id):
        waiting = connection.execute('SELECT conversation_key FROM interaction_waits WHERE message_id=?', (message_id,)).fetchall()
        connection.execute('DELETE FROM interaction_waits WHERE message_id=?', (message_id,))
        if any(row[0] in self.context_keys('local') for row in waiting):
            row = connection.execute('SELECT payload FROM agency_state WHERE id=1').fetchone()
            try:
                state = json.loads(row[0]) if row else {}
                if state.get('status') == 'waiting':
                    state.update(status='blocked', next_step='', resume_at='', plan_revision=uuid.uuid4().hex)
                    connection.execute('UPDATE agency_state SET payload=? WHERE id=1', (json.dumps(state, ensure_ascii=False),))
            except (ValueError, TypeError, AttributeError):
                pass

    def delete_history_records(self, ids: list[int]) -> tuple[int, list[str], list[str]]:
        """一次事务删除已确认的历史消息；不修改长期记忆内容。"""
        audio_paths, attachment_paths = [], []
        deleted = 0
        with self._connect() as connection:
            for message_id in set(ids):
                self._clear_interaction_wait(connection, message_id)
                attachment_paths.extend(row[0] for row in connection.execute(
                    'SELECT local_path FROM message_attachments WHERE message_id=?', (message_id,)))
                audio_paths.extend(row[0] for row in connection.execute(
                    'SELECT a.file_path FROM audio_files a JOIN audio_batches b ON a.batch_id=b.batch_id WHERE b.message_id=?',
                    (message_id,)))
                connection.execute('DELETE FROM audio_files WHERE batch_id IN (SELECT batch_id FROM audio_batches WHERE message_id=?)', (message_id,))
                for table in ('audio_batches', 'message_attachments', 'message_extras',
                              'hidden_messages', 'command_traces', 'memory_sources', 'owner_notifications', 'dsh_import_items'):
                    connection.execute(f'DELETE FROM {table} WHERE message_id=?', (message_id,))
                connection.execute("DELETE FROM message_extras WHERE kind='quote' AND target=?", (str(message_id),))
                deleted += connection.execute('DELETE FROM messages WHERE id=?', (message_id,)).rowcount
        return deleted, audio_paths, attachment_paths

    def save_extras(self, message_id: int, extras: list[dict]) -> None:
        with self._connect() as connection:
            connection.executemany('INSERT OR IGNORE INTO message_extras VALUES (?, ?, ?)',
                                   [(message_id, x['kind'], x['target']) for x in extras])

    def set_video_session(self, conversation_key: str, message_id: int, manifest: dict) -> None:
        with self._connect() as connection:
            connection.execute('INSERT OR REPLACE INTO conversation_video VALUES (?, ?, ?)',
                               (conversation_key, message_id, json.dumps(manifest, ensure_ascii=False)))

    def get_video_session(self, conversation_key: str) -> dict:
        scope, keys = self.context_scope(conversation_key, 'v.conversation_key')
        with self._connect() as connection:
            row = connection.execute(
                'SELECT v.manifest, v.message_id FROM conversation_video v JOIN messages m ON m.id=v.message_id '
                'WHERE ' + scope + ' AND NOT EXISTS '
                '(SELECT 1 FROM hidden_messages h WHERE h.message_id=v.message_id) ORDER BY v.message_id DESC LIMIT 1',
                keys).fetchone()
        try:
            return {**json.loads(row[0]), "_message_id": row[1]} if row else {}
        except (ValueError, TypeError):
            return {}

    def get_extras(self, message_id: int) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute('SELECT kind, target FROM message_extras WHERE message_id=?', (message_id,)).fetchall()
        return [dict(row) for row in rows]

    def set_context_cutoff(self, conversation_key: str, after_id: int = 0) -> None:
        """Bind an optional style boundary to an actual message in this database."""
        with self._connect() as connection:
            if after_id <= 0:
                connection.execute('DELETE FROM context_settings WHERE conversation_key=?', (conversation_key,))
                return
            row = connection.execute('SELECT id,content,created_at FROM messages WHERE id=? AND conversation_key=?',
                                     (after_id, conversation_key)).fetchone()
            if row is None:
                raise ValueError('风格起点必须对应当前数据库中的消息。')
            anchor = {'id': row['id'], 'created_at': row['created_at'],
                      'content_sha256': hashlib.sha256(row['content'].encode('utf-8')).hexdigest()}
            connection.execute('INSERT INTO context_settings VALUES (?,?) ON CONFLICT(conversation_key) '
                               'DO UPDATE SET style_anchor=excluded.style_anchor',
                               (conversation_key, json.dumps(anchor, ensure_ascii=False)))

    def context_cutoff(self, conversation_key: str = 'local') -> int:
        with self._connect() as connection:
            setting = connection.execute('SELECT style_anchor FROM context_settings WHERE conversation_key=?',
                                         (conversation_key,)).fetchone()
            if setting is None:
                return 0
            try:
                anchor = json.loads(setting[0])
                row = connection.execute('SELECT id,content,created_at FROM messages WHERE id=? AND conversation_key=?',
                                         (anchor['id'], conversation_key)).fetchone()
                if (row and row['created_at'] == anchor['created_at']
                        and hashlib.sha256(row['content'].encode('utf-8')).hexdigest() == anchor['content_sha256']):
                    return max(0, int(row['id']))
            except (ValueError, TypeError, KeyError):
                pass
        return 0

    def get_context_messages(self, conversation_key: str, limit: int = 24, through_id: int | None = None) -> list[dict]:
        scope, keys = self.context_scope(conversation_key)
        with self._connect() as connection:
            boundary = ' AND id <= ?' if through_id is not None else ''
            values = [*keys, int(through_id), limit] if through_id is not None else [*keys, limit]
            rows = connection.execute(
                "SELECT id, role, content, created_at, conversation_key, source FROM messages "
                "WHERE " + scope + " AND role IN ('user', 'assistant') "
                "AND NOT EXISTS(SELECT 1 FROM message_extras e WHERE e.message_id=messages.id AND e.kind='internal_activity')" + boundary +
                " ORDER BY id DESC LIMIT ?", values,
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def get_messages_for_local_date(self, conversation_key: str, local_date: str,
                                    through_id: int | None = None) -> list[dict]:
        """Return a day's archived messages for explicit date-based questions."""
        scope, keys = self.archive_scope(conversation_key)
        with self._connect() as connection:
            boundary = ' AND id <= ?' if through_id is not None else ''
            values = [*keys, local_date, int(through_id)] if through_id is not None else [*keys, local_date]
            rows = connection.execute(
                "SELECT id,role,content,created_at,conversation_key,source FROM messages "
                "WHERE " + scope + " AND substr(created_at,1,10)=? AND role IN ('user','assistant')" +
                boundary + ' ORDER BY id DESC LIMIT 100', values,
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def configure_owner_link(self, peer):
        """Physical rows stay unchanged; only this explicitly bound identity shares reads."""
        peer = str(peer or '').strip()
        self._owner_peer = peer if re.fullmatch(r'[0-9]{5,12}', peer) else ''

    def context_keys(self, conversation_key):
        peer = self._owner_peer
        if peer and conversation_key in ('local', 'qq:'+peer):
            return ('local', 'qq:'+peer)
        return (conversation_key,)

    def context_scope(self, conversation_key, column='conversation_key'):
        if not re.fullmatch(r'(?:[a-z]+\.)?conversation_key', column):
            raise ValueError('Invalid conversation scope column')
        keys = self.context_keys(conversation_key)
        return column+' IN ('+','.join('?' for _ in keys)+')', list(keys)

    def archive_scope(self, conversation_key, column='conversation_key'):
        """Owner memory is shared across modes; recent dialogue stays in its lane."""
        scope, keys = self.context_scope(conversation_key, column)
        if conversation_key == 'local:work' or 'local' in self.context_keys(conversation_key):
            keys = list(dict.fromkeys((*self.context_keys('local'), 'local:work')))
            return '(' + column+' IN ('+','.join('?' for _ in keys)+') OR '+column+" LIKE 'dsh:%')", keys
        return scope, keys

    def archive_accessible(self, conversation_key, target):
        owner = conversation_key == 'local:work' or 'local' in self.context_keys(conversation_key)
        return target in self.context_keys(conversation_key) or (owner and (
            target in (*self.context_keys('local'), 'local:work') or target.startswith('dsh:')))

    def get_recent_local_messages(self, limit: int = 24) -> list[dict]:
        return self.get_context_messages("local", limit)

    def save_attachment(self, message_id: int, attachment: dict) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO message_attachments
                    (message_id, file_name, kind, mime_type, local_path, extracted_text, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(message_id),
                    str(attachment.get("file_name", "附件")),
                    str(attachment.get("kind", "document")),
                    str(attachment.get("mime_type", "")),
                    str(attachment.get("local_path", "")),
                    str(attachment.get("extracted_text", "")),
                    int(attachment.get("size_bytes", 0)),
                ),
            )

    def attachments_for_message(self, message_id: int) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM message_attachments WHERE message_id = ? ORDER BY id",
                (int(message_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_api_usage(
        self,
        model: str,
        request_kind: str,
        usage: dict,
        request_id: str = "",
    ) -> None:
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)
        cached_tokens = int(usage.get("cached_tokens", 0) or 0)
        if total_tokens <= 0:
            return
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO api_usage
                    (model, request_kind, prompt_tokens, completion_tokens, total_tokens,
                     cached_tokens, request_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(model), str(request_kind), prompt_tokens, completion_tokens,
                    total_tokens, cached_tokens, str(request_id), self._now(),
                ),
            )

    def api_usage_summary(self, local_date: str | None = None) -> dict:
        def totals(where: str = "", params: tuple = ()) -> dict:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT COUNT(*) AS requests,
                           COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                           COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                           COALESCE(SUM(total_tokens), 0) AS total_tokens,
                           COALESCE(SUM(cached_tokens), 0) AS cached_tokens
                    FROM api_usage
                    """ + where,
                    params,
                ).fetchone()
            return dict(row)

        today = local_date or self._now()[:10]
        return {"today": totals(" WHERE substr(created_at, 1, 10) = ?", (today,)),
                "all_time": totals()}

    def api_usage_details(self) -> dict:
        """Read usage categories without treating cached input as extra tokens."""
        with self._connect() as connection:
            rows = connection.execute('''SELECT request_kind, SUM(total_tokens) AS total_tokens
                FROM api_usage WHERE substr(created_at,1,10)=? GROUP BY request_kind''',
                (self._now()[:10],)).fetchall()
            latest = connection.execute('''SELECT created_at,request_kind,prompt_tokens,completion_tokens,total_tokens
                FROM api_usage WHERE request_kind IN ('chat','qq_chat') ORDER BY id DESC LIMIT 1''').fetchone()
        return {'today_by_kind': {row['request_kind']: int(row['total_tokens']) for row in rows},
                'latest_chat': dict(latest) if latest else {}}

    def delete_message(self, message_id: int) -> tuple[bool, int, list[str], list[str]]:
        """Delete one message and auto memories that have no remaining source messages."""
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM messages WHERE id = ?", (message_id,)
            ).fetchone()
            if exists is None:
                return False, 0, [], []
            self._clear_interaction_wait(connection, message_id)

            attachment_rows = connection.execute(
                "SELECT local_path FROM message_attachments WHERE message_id = ?",
                (message_id,),
            ).fetchall()
            connection.execute('DELETE FROM message_extras WHERE message_id=?', (message_id,))
            connection.execute('DELETE FROM hidden_messages WHERE message_id=?', (message_id,))
            connection.execute('DELETE FROM owner_notifications WHERE message_id=?', (message_id,))
            connection.execute('DELETE FROM command_traces WHERE message_id=?', (message_id,))
            connection.execute('DELETE FROM dsh_import_items WHERE message_id=?', (message_id,))
            attachment_paths = [str(row["local_path"]) for row in attachment_rows]
            connection.execute(
                "DELETE FROM message_attachments WHERE message_id = ?", (message_id,)
            )

            audio_rows = connection.execute(
                """
                SELECT audio_files.file_path FROM audio_files
                JOIN audio_batches ON audio_batches.batch_id = audio_files.batch_id
                WHERE audio_batches.message_id = ?
                """,
                (message_id,),
            ).fetchall()
            audio_paths = [str(row["file_path"]) for row in audio_rows]
            batch_rows = connection.execute(
                "SELECT batch_id FROM audio_batches WHERE message_id = ?", (message_id,)
            ).fetchall()
            batch_ids = [str(row["batch_id"]) for row in batch_rows]
            if batch_ids:
                placeholders = ",".join("?" for _ in batch_ids)
                connection.execute(
                    f"DELETE FROM audio_files WHERE batch_id IN ({placeholders})", batch_ids
                )
                connection.execute(
                    f"DELETE FROM audio_batches WHERE batch_id IN ({placeholders})", batch_ids
                )

            affected_memories = [row[0] for row in connection.execute(
                "SELECT memory_id FROM memory_sources WHERE message_id = ?", (message_id,))]
            connection.execute("DELETE FROM memory_sources WHERE message_id = ?", (message_id,))

            # 只清除本条消息关联的无来源自动记忆，避免误删历史管理中独立保留的记忆。
            orphaned = connection.execute(
                """
                SELECT id FROM memories
                WHERE source = 'deepseek'
                  AND NOT EXISTS (
                      SELECT 1 FROM memory_sources
                      WHERE memory_sources.memory_id = memories.id
                  )
                """
            ).fetchall()
            orphan_ids = [int(row["id"]) for row in orphaned if row["id"] in affected_memories]
            if orphan_ids:
                placeholders = ",".join("?" for _ in orphan_ids)
                connection.execute(
                    f"DELETE FROM memory_sources WHERE memory_id IN ({placeholders})",
                    orphan_ids,
                )
                removed_memories = connection.execute(
                    f"DELETE FROM memories WHERE id IN ({placeholders})",
                    orphan_ids,
                ).rowcount
            else:
                removed_memories = 0

            connection.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            return True, removed_memories, audio_paths, attachment_paths

    def create_audio_batch(self, batch_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO audio_batches (batch_id, message_id) VALUES (?, NULL)",
                (batch_id,),
            )

    def link_audio_batch(self, batch_id: str, message_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE audio_batches SET message_id = ? WHERE batch_id = ?",
                (message_id, batch_id),
            )
            return cursor.rowcount > 0

    def record_audio_file(self, batch_id: str, file_path: str) -> bool:
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM audio_batches WHERE batch_id = ?", (batch_id,)
            ).fetchone()
            if exists is None:
                return False
            connection.execute(
                "INSERT INTO audio_files (batch_id, file_path, created_at) VALUES (?, ?, ?)",
                (batch_id, file_path, self._now()),
            )
            return True

    def audio_files_for_message(self, message_id: int) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT audio_files.file_path FROM audio_files
                JOIN audio_batches ON audio_batches.batch_id = audio_files.batch_id
                WHERE audio_batches.message_id = ? ORDER BY audio_files.id
                """,
                (message_id,),
            ).fetchall()
        return [str(row["file_path"]) for row in rows]

    def delete_audio_batch(self, batch_id: str) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT file_path FROM audio_files WHERE batch_id = ?", (batch_id,)
            ).fetchall()
            connection.execute("DELETE FROM audio_files WHERE batch_id = ?", (batch_id,))
            connection.execute("DELETE FROM audio_batches WHERE batch_id = ?", (batch_id,))
        return [str(row["file_path"]) for row in rows]

    def clear_audio_history(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute("SELECT file_path FROM audio_files").fetchall()
            connection.execute("DELETE FROM audio_files")
            connection.execute("DELETE FROM audio_batches")
        return [str(row["file_path"]) for row in rows]

    def list_memories(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM memories ORDER BY id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def active_memories(self, limit: int = 12, query: str = "", char_budget: int = 2000, include_recent: bool = True,
                        conversation_key: str | None = None) -> list[dict]:
        """相关条目优先，少量最近条目兜底；限制每轮上下文体积。"""
        from standard_memory import terms
        words = terms(query)[:40]
        scope, scope_args = '', []
        if conversation_key is not None:
            sql, keys = self.archive_scope(conversation_key, 'm.conversation_key')
            manual = int(conversation_key == 'local:work' or 'local' in self.context_keys(conversation_key))
            scope = (' AND ((EXISTS(SELECT 1 FROM memory_sources s JOIN messages m ON m.id=s.message_id '
                     'WHERE s.memory_id=memories.id AND '+sql+') AND NOT EXISTS('
                     'SELECT 1 FROM memory_sources s JOIN messages m ON m.id=s.message_id '
                     'WHERE s.memory_id=memories.id AND NOT ('+sql+'))) OR '
                     '(?=1 AND NOT EXISTS(SELECT 1 FROM memory_sources s WHERE s.memory_id=memories.id)))')
            scope_args = [*keys, *keys, manual]
        with self._connect() as connection:
            recent = connection.execute("SELECT * FROM memories WHERE status='active'"+scope+
                                        " ORDER BY updated_at DESC,id DESC LIMIT 4", scope_args).fetchall()
            relevant = []
            if words:
                where = " OR ".join("instr(lower(content),?)>0" for _ in words)
                relevant = connection.execute("SELECT * FROM memories WHERE status='active'"+scope+" AND (" + where +
                                              ") ORDER BY updated_at DESC,id DESC", [*scope_args, *words]).fetchall()
                relevant = sorted(relevant, key=lambda row: len(set(words) & set(terms(row["content"]))), reverse=True)
            rows = [*relevant[:limit], *(recent if include_recent else [])]
        result, seen, remaining = [], set(), max(0, char_budget)
        for row in rows:
            if row["id"] in seen or len(result) >= limit:
                continue
            seen.add(row["id"])
            content = row["content"]
            # 不截断单条事实，避免把否定或限定条件切掉。
            if len(content) > remaining:
                continue
            remaining -= len(content)
            result.append(dict(row))
        return result

    def search_long_memories(self, query: str, conversation_key: str | None = None) -> list[dict]:
        from standard_memory import terms
        words = terms(query)[:40]
        if not words:
            return []
        return self.active_memories(limit=6, query=query, char_budget=4000, include_recent=False, conversation_key=conversation_key)

    def add_memory(
        self,
        content: str,
        status: str = "active",
        source: str = "manual",
        message_ids: list[int] | None = None,
    ) -> int | None:
        cleaned = content.strip()
        if not cleaned:
            return None

        normalized = cleaned.casefold()
        now = self._now()
        with self._connect() as connection:
            valid_message_ids: list[int] = []
            for message_id in dict.fromkeys(int(value) for value in (message_ids or [])):
                exists = connection.execute(
                    "SELECT 1 FROM messages WHERE id = ?", (message_id,)
                ).fetchone()
                if exists is not None:
                    valid_message_ids.append(message_id)
            if message_ids and not valid_message_ids:
                # An extraction may finish after its source message was deleted.
                return None

            existing_rows = connection.execute("SELECT * FROM memories").fetchall()
            existing = next(
                (row for row in existing_rows if row["content"].strip().casefold() == normalized),
                None,
            )
            if existing is not None:
                memory_id = int(existing["id"])
                if source == "deepseek" and existing["source"] == "deepseek":
                    if status == "active" and existing["status"] != "active":
                        connection.execute(
                            "UPDATE memories SET status = 'active', updated_at = ? WHERE id = ?",
                            (now, memory_id),
                        )
                    connection.executemany(
                        "INSERT OR IGNORE INTO memory_sources (memory_id, message_id) VALUES (?, ?)",
                        [(memory_id, message_id) for message_id in valid_message_ids],
                    )
                return None

            cursor = connection.execute(
                """
                INSERT INTO memories (content, status, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cleaned, status, source, now, now),
            )
            memory_id = int(cursor.lastrowid)
            if source == "deepseek":
                connection.executemany(
                    "INSERT OR IGNORE INTO memory_sources (memory_id, message_id) VALUES (?, ?)",
                    [(memory_id, message_id) for message_id in valid_message_ids],
                )
            return memory_id

    def update_memory(self, memory_id: int, content: str) -> bool:
        cleaned = content.strip()
        if not cleaned:
            return False
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE memories SET content = ?, source = 'manual', updated_at = ? WHERE id = ?",
                (cleaned, self._now(), memory_id),
            )
            if cursor.rowcount > 0:
                # 用户修订后作为手动记忆保留，删除原消息不再连带删除它。
                connection.execute("DELETE FROM memory_sources WHERE memory_id = ?", (memory_id,))
            return cursor.rowcount > 0

    def approve_memory(self, memory_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE memories SET status = 'active', updated_at = ? WHERE id = ?",
                (self._now(), memory_id),
            )
            return cursor.rowcount > 0

    def delete_memory(self, memory_id: int) -> bool:
        with self._connect() as connection:
            connection.execute("DELETE FROM memory_sources WHERE memory_id = ?", (memory_id,))
            cursor = connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cursor.rowcount > 0

