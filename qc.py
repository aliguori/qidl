import sys, json

class Input(object):
    def __init__(self, fp):
        self.fp = fp
        self.buf = ''
        self.eof = False

    def pop(self):
        if len(self.buf) == 0:
            if self.eof:
                return ''

            data = self.fp.read(1024)
            if data == '':
                self.eof = True
                return ''

            self.buf += data

        ch = self.buf[0]
        self.buf = self.buf[1:]
        return ch

def in_range(ch, start, end):
    if ch >= start and ch <= end:
        return True
    return False

# D			[0-9]
# L			[a-zA-Z_]
# H			[a-fA-F0-9]
# E			[Ee][+-]?{D}+
# FS			(f|F|l|L)
# IS			(u|U|l|L)*

def is_D(ch):
    return in_range(ch, '0', '9')

def is_L(ch):
    return in_range(ch, 'a', 'z') or in_range(ch, 'A', 'Z') or ch == '_'

def is_H(ch):
    return in_range(ch, 'a', 'f') or in_range(ch, 'A', 'F') or is_D(ch)

def is_FS(ch):
    return ch in 'fFlL'

def is_IS(ch):
    return ch in 'uUlL'

def lexer(fp):
    ch = fp.pop()

    while not fp.eof:
        token = ''

        if is_L(ch):
            token += ch

            ch = fp.pop()
            while is_L(ch) or is_D(ch):
                token += ch
                ch = fp.pop()
            if token in [ 'auto', 'break', 'case', 'const', 'continue',
                           'default', 'do', 'else', 'enum', 'extern',
                           'for', 'goto', 'if', 'register', 'return', 'signed',
                           'sizeof',
                           'static', 'struct', 'typedef', 'union', 'unsigned',
                           'volatile', 'while' ]:
                yield (token, token)
            else:
                yield ('symbol', token)
        elif ch == "'":
            token += ch

            ch = fp.pop()
            if ch == '\\':
                token += ch
                token += fp.pop()
            else:
                token += ch
            token += fp.pop()
            ch = fp.pop()
            yield ('literal', token)
        elif ch == '"':
            token += ch

            ch = fp.pop()
            while ch not in ['', '"']:
                token += ch
                if ch == '\\':
                    token += fp.pop()
                ch = fp.pop()
            token += ch
            yield ('literal', token)
            ch = fp.pop()
        elif ch in '.><+-*/%&^|!;{},:=()[]~?':
            token += ch
            ch = fp.pop()
            tmp_token = token + ch
            if tmp_token in ['<:']:
                yield ('operator', '[')
                ch = fp.pop()
            elif tmp_token in [':>']:
                yield ('operator', ']')
                ch = fp.pop()
            elif tmp_token in ['<%']:
                yield ('operator', '{')
                ch = fp.pop()
            elif tmp_token in ['%>']:
                yield ('operator', '}')
                ch = fp.pop()
            elif tmp_token == '//':
                token = tmp_token
                ch = fp.pop()
                while ch != '\n' and ch != '':
                    token += ch
                    ch = fp.pop()
                yield ('comment', token)
            elif tmp_token == '/*':
                token = tmp_token

                ch = fp.pop()
                while True:
                    while ch != '*':
                        token += ch
                        ch = fp.pop()
                    token += ch
                    ch = fp.pop()
                    if ch == '/':
                        token += ch
                        break
                yield ('comment', token)
                ch = fp.pop()
            elif tmp_token in [ '+=', '-=', '*=', '/=', '%=', '&=', '^=',
                                '|=', '>>', '<<', '++', '--', '->', '&&',
                                '||', '<=', '>=', '==', '!=' ]:
                yield ('operator', tmp_token)
                ch = fp.pop()
            else:
                yield ('operator', token)
        elif ch == '0':
            token += ch
            ch = fp.pop()
            if ch in 'xX':
                token += ch
                ch = fp.pop()
                while is_H(ch):
                    token += ch
                    ch = fp.pop()
                while is_IS(ch):
                    token += ch
                    ch = fp.pop()
            elif is_D(ch):
                token += ch
                ch = fp.pop()
                while is_D(ch):
                    token += ch
                    ch = fp.pop()
            yield ('literal', token)
        elif is_D(ch):
            token += ch
            ch = fp.pop()
            while is_D(ch):
                token += ch
                ch = fp.pop()
            yield ('literal', token)
        elif ch in ' \t\v\n\f':
            token += ch
            ch = fp.pop()
            while len(ch) and ch in ' \t\v\n\f':
                token += ch
                ch = fp.pop()
            yield ('whitespace', token)
        elif ch in '#':
            token += ch
            ch = fp.pop()
            while len(ch) and ch != '\n':
                token += ch
                ch = fp.pop()
            yield ('directive', token)
        else:
            yield ('unknown', ch)
            ch = fp.pop()

class LookAhead(object):
    def __init__(self, container):
        self.i = container.__iter__()
        self.la = []
        self.full = False

    def at(self, i):
        if i >= len(self.la):
            if self.full:
                raise StopIteration()
            else:
                try:
                    self.la.append(self.i.next())
                except StopIteration, e:
                    self.full = True
                    raise StopIteration()

        return self.la[i]

    def eof(self):
        try:
            self.at(len(self.la))
        except StopIteration, e:
            return True

        return False

def skip(c):
    for token, value in c:
        if token in ['whitespace', 'comment', 'directive']:
            continue
        yield (token, value)

def expect(la, index, first, second=None):
    if la.at(index)[0] != first:
        raise Exception("expected '%s', got %s %s" % (first, la.at(index)[0], la.at(index)[1]))
    if second != None:
        if la.at(index)[1] != second:
            raise Exception("expected '%s', got %s" % (second, la.at(index)[1]))
    return index + 1, la.at(index)[1]

def choice(la, index, first, second=None):
    if la.at(index)[0] != first:
        return False
    if second != None:
        if la.at(index)[1] != second:
            return False
    return True

def parse_markers(la, index, ret):
    next = index

    found_marker = True
    while choice(la, next, 'symbol') and found_marker:
        if choice(la, next, 'symbol', '_derived'):
            next += 1
            ret['is_derived'] = True
        elif choice(la, next, 'symbol', '_immutable'):
            next += 1
            ret['is_immutable'] = True
        elif choice(la, next, 'symbol', '_broken'):
            next += 1
            ret['is_broken'] = True
        elif choice(la, next, 'symbol', '_size_is'):
            next += 1

            next, _ = expect(la, next, 'operator', '(')
            next, array_size = expect(la, next, 'symbol')
            next, _ = expect(la, next, 'operator', ')')

            ret['is_array'] = True
            ret['array_size'] = 's->%s' % array_size
        elif choice(la, next, 'symbol', '_default'):
            next += 1

            next, _ = expect(la, next, 'operator', '(')
            next, default = expect(la, next, 'literal')
            next, _ = expect(la, next, 'operator', ')')

            ret['default'] = default
        elif choice(la, next, 'symbol', '_type_of'):
            next += 1

            next, _ = expect(la, next, 'operator', '(')
            next, typename = expect(la, next, 'symbol')
            next, _ = expect(la, next, 'operator', ')')

            ret['is_container'] = True
            ret['type_of'] = typename
        else:
            found_marker = False

    if ret['type'] in ['GSList']:
        ret['is_container'] = True

    return (next - index), ret

def parse_type(la, index):
    next = index

    typename = ''
    if choice(la, next, 'const', 'const'):
        typename += 'const '
        next += 1

    if choice(la, next, 'struct', 'struct'):
        typename += 'struct '
        next += 1

    next, rest = expect(la, next, 'symbol')
    typename += rest

    ret = { 'type': typename }

    off, ret = parse_markers(la, next, ret)
    next += off

    if choice(la, next, 'operator', '*'):
        next += 1
        ret['is_pointer'] = True

    return (next - index), ret

def parse_var_decl(la, index):
    next = index

    off, ret = parse_type(la, next)
    next += off

    next, variable = expect(la, next, 'symbol')
    ret['variable'] = variable

    if choice(la, next, 'operator', '['):
        next += 1

        if not ret.has_key('is_array'):
            ret['is_array'] = True
            ret['array_size'] = la.at(next)[1]
        else:
            ret['array_capacity'] = la.at(next)[1]
        next += 1

        next, _ = expect(la, next, 'operator', ']')

    off, ret = parse_markers(la, next, ret)
    next += off

    return (next - index), ret

def parse_struct(la, index):
    next = index

    next, _ = expect(la, next, 'struct', 'struct')

    name = None
    if choice(la, next, 'symbol'):
        name = la.at(next)[1]
        next += 1

    next, _ = expect(la, next, 'operator', '{')

    nodes = []

    while not choice(la, next, 'operator', '}'):
        offset, node = parse_var_decl(la, next)
        next += offset
        nodes.append(node)

        next, _ = expect(la, next, 'operator', ';')

    next += 1

    return (next - index), { 'struct': name, 'fields': nodes }

def parse_typedef(la, index):
    next = index

    next, _ = expect(la, next, 'typedef', 'typedef')

    offset, node = parse_struct(la, next)
    next += offset

    next, typename = expect(la, next, 'symbol')

    return (next - index), { 'typedef': typename, 'type': node }

def parse_func_decl(la, index):
    next = index

    off, returns = parse_type(la, index)
    next += off

    next, name = expect(la, next, 'symbol')
    next, _ = expect(la, next, 'operator', '(')

    args = []
    while not choice(la, next, 'operator', ')'):
        if len(args) != 0:
            next, _ = expect(la, next, 'operator', ',')

        off, arg = parse_var_decl(la, next)
        next += off
        args.append(arg)

    next, _ = expect(la, next, 'operator', ')')

    ret = { 'returns': returns, 'func': name, 'args': args }

    return (next - index), ret

def parse(la, index=0):
    next = index

    nodes = []
    while True:
        try:
            if choice(la, next, 'typedef'):
                offset, node = parse_typedef(la, next)
            elif choice(la, next, 'struct'):
                offset, node = parse_struct(la, next)
            else:
                offset, node = parse_func_decl(la, next)

            next, _ = expect(la, next + offset, 'operator', ';')
        except StopIteration, e:
            break

        nodes.append(node)

    return (next - index), nodes

if __name__ == '__main__':
    la = LookAhead(skip(lexer(Input(sys.stdin))))
    _, nodes = parse(la)
    print json.dumps(nodes, sort_keys=True, indent=2)

    

