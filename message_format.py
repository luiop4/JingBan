"""聊天代码块解析与流式语音过滤，不执行任何代码。"""
import re


OPEN_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def message_parts(text):
    """返回（语言或 None，内容）；尚未闭合的代码块也能显示。"""
    parts, lines = [], []
    fence, language = "", None
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if fence:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", stripped):
                parts.append((language, "".join(lines)))
                lines, fence, language = [], "", None
            else:
                lines.append(line)
        else:
            match = OPEN_FENCE.match(stripped)
            if match:
                if lines:
                    parts.append((None, "".join(lines)))
                lines = []
                fence = match[1]
                language = match[2].strip() or "代码"
            else:
                lines.append(line)
    if lines or fence:
        parts.append((language, "".join(lines)))
    return parts


class SpeechCodeFilter:
    """保留正文的实时输出；行首围栏未收全时先缓存，避免代码泄漏给 TTS。"""
    def __init__(self):
        self.line = ""
        self.prose = False
        self.fence = ""
        self.inline = False

    def feed(self, text, flush=False):
        output = []
        for char in text:
            if self.prose:
                if char == "`":
                    self.inline = not self.inline
                elif not self.inline:
                    output.append(char)
                if char == "\n":
                    self.prose = False
                    self.inline = False
                continue
            self.line += char
            if char == "\n":
                self._finish_line(output)
            elif not self.fence:
                prefix = self.line.lstrip(" ")
                # 一旦确定不是围栏，这一行即可实时朗读。
                if (len(self.line) - len(prefix) > 3 or
                        (prefix and prefix[0] not in "`~")):
                    self.prose = True
                    output.append(self.line)
                    self.line = ""
        if flush:
            if self.line:
                self._finish_line(output)
            self.inline = False
        return "".join(output)

    def _finish_line(self, output):
        line = self.line.rstrip("\r\n")
        if self.fence:
            if re.fullmatch(r" {0,3}" + re.escape(self.fence[0]) + "{" + str(len(self.fence)) + r",}\s*", line):
                self.fence = ""
                output.append("\n")
        else:
            match = OPEN_FENCE.match(line)
            if match:
                self.fence = match[1]
                output.append("\n")
            else:
                output.append(re.sub(r"`+[^`]*`+", "", self.line))
        self.line = ""


def speech_text(text):
    return SpeechCodeFilter().feed(text, flush=True).strip()
