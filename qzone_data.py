"""Read Qzone's JavaScript data literals without executing JavaScript."""
import json
import re


def decode_literal(source):
    index, nodes = 0, 0

    def space():
        nonlocal index
        while index < len(source):
            if source[index].isspace():
                index += 1
            elif source.startswith('//', index):
                end = source.find('\n', index+2)
                index = len(source) if end < 0 else end+1
            elif source.startswith('/*', index):
                end = source.find('*/', index+2)
                if end < 0:
                    raise ValueError('unfinished comment')
                index = end+2
            else:
                break

    def string():
        nonlocal index
        quote = source[index]
        index += 1
        output = []
        escapes = {'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t', 'v': '\v',
                   '0': '\0', "'": "'", '"': '"', '/': '/', '\\': '\\'}
        while index < len(source):
            char = source[index]
            index += 1
            if char == quote:
                return ''.join(output).encode('utf-16-le', 'surrogatepass').decode('utf-16-le', 'replace')
            if char in '\r\n':
                raise ValueError('newline in string')
            if char == '\\':
                if index >= len(source):
                    break
                char = source[index]
                index += 1
                if char in '\r\n':
                    if char == '\r' and source[index:index+1] == '\n':
                        index += 1
                    continue
                if char in ('x', 'u'):
                    length = 2 if char == 'x' else 4
                    digits = source[index:index+length]
                    if len(digits) != length or not re.fullmatch('[0-9a-fA-F]+', digits):
                        raise ValueError('invalid escape')
                    output.append(chr(int(digits, 16)))
                    index += length
                    continue
                if char not in escapes:
                    raise ValueError('unsupported escape')
                char = escapes[char]
            output.append(char)
        raise ValueError('unfinished string')

    def value(depth=0):
        nonlocal index, nodes
        nodes += 1
        if depth > 64 or nodes > 100000:
            raise ValueError('data limit exceeded')
        space()
        char = source[index:index+1]
        if char in ('"', "'"):
            return string()
        if char in ('{', '['):
            object_ = char == '{'
            result = {} if object_ else []
            close = '}' if object_ else ']'
            index += 1
            space()
            while source[index:index+1] != close:
                key = None
                if object_:
                    if source[index:index+1] in ('"', "'"):
                        key = string()
                    else:
                        match = re.match(r'[A-Za-z_$][\w$]*', source[index:])
                        if not match:
                            raise ValueError('invalid key')
                        key = match[0]
                        index += len(key)
                    space()
                    if source[index:index+1] != ':' or key in result:
                        raise ValueError('invalid or duplicate key')
                    index += 1
                item = value(depth+1)
                if object_:
                    result[key] = item
                else:
                    result.append(item)
                space()
                if source[index:index+1] == close:
                    break
                if source[index:index+1] != ',':
                    raise ValueError('invalid separator')
                index += 1
                space()
            index += 1
            return result
        for literal, result in (('true', True), ('false', False), ('null', None), ('undefined', None)):
            if source.startswith(literal, index):
                index += len(literal)
                return result
        match = re.match(r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?', source[index:])
        if not match:
            raise ValueError('not a data literal')
        index += len(match[0])
        return json.loads(match[0])

    try:
        result = value()
    except (ValueError, RecursionError) as error:
        raise ValueError(str(error)+' at offset '+str(index)+' line '+str(source[:index].count('\n')+1)+
                         ' character U+'+format(ord(source[index]) if index < len(source) else 0, '04X')) from None
    return result, index
