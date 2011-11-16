import sys

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
                           'void', 'volatile', 'while' ]:
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

def parse_type(la, index):
    next = index

    typename = ''
    if choice(la, next, 'struct', 'struct'):
        typename = 'struct '
        next += 1

    next, rest = expect(la, next, 'symbol')
    typename += rest

    ret = { 'type': typename }

    if choice(la, next, 'symbol', '_derived'):
        next += 1
        ret['is_derived'] = True
    elif choice(la, next, 'symbol', '_immutable'):
        next += 1
        ret['is_immutable'] = True
    elif choice(la, next, 'symbol', '_broken'):
        next += 1
        ret['is_broken'] = True
    elif choice(la, next, 'symbol', '_version'):
        next += 1

        next, _ = expect(la, next, 'operator', '(')
        next, version = expect(la, next, 'literal')
        next, _ = expect(la, next, 'operator', ')')

        ret['version'] = version
    elif choice(la, next, 'symbol', '_size_is'):
        next += 1

        next, _ = expect(la, next, 'operator', '(')
        next, array_size = expect(la, next, 'symbol')
        next, _ = expect(la, next, 'operator', ')')

        ret['is_array'] = True
        ret['array_size'] = 's->%s' % array_size
        

    if choice(la, next, 'operator', '*'):
        next += 1
        ret['is_pointer'] = True

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

    if choice(la, next, 'symbol', '_default'):
        next += 1

        next, _ = expect(la, next, 'operator', '(')
        next, default = expect(la, next, 'literal')
        next, _ = expect(la, next, 'operator', ')')

        ret['default'] = default

    next, _ = expect(la, next, 'operator', ';')

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
        offset, node = parse_type(la, next)
        next += offset
        nodes.append(node)

    next += 1

    return (next - index), { 'struct': name, 'fields': nodes }

def parse_typedef(la, index):
    next = index

    next, _ = expect(la, next, 'typedef', 'typedef')

    offset, node = parse_struct(la, next)
    next += offset

    next, typename = expect(la, next, 'symbol')

    return (next - index), { 'typedef': typename, 'type': node }

def qapi_format(node, is_save=True):
    if node.has_key('typedef'):
        dtype = node['typedef']
        fields = node['type']['fields']
    else:
        dtype = node['struct']
        fields = node['fields']

    if is_save:
        print 'void qc_save_%s(Visitor *v, %s *s, const char *name, Error **errp)' % (dtype, dtype)
    else:
        print 'void qc_load_%s(Visitor *v, %s *s, const char *name, Error **errp)' % (dtype, dtype)
    print '{'
    print '    visit_start_struct(v, "%s", name, errp);' % (dtype)
    for field in fields:
        if field.has_key('is_derived') or field.has_key('is_immutable') or field.has_key('is_broken'):
            continue

        if field['type'].endswith('_t'):
            typename = field['type'][:-2]
        else:
            typename = field['type']

        if field.has_key('is_array'):
            if field.has_key('array_capacity'):
                print '    if (%(array_size)s > %(array_capacity)s) {' % field
                print '        error_set(errp, QERR_FAULT, "Array size greater than capacity.");'
                print '    }'
                print '    %(array_size)s = MIN(%(array_size)s, %(array_capacity)s);' % field
            print '    visit_start_array(v, "%s", errp);' % (field['variable'])
            print '    for (size_t i = 0; i < %s; i++) {' % (field['array_size'])
            print '        visit_type_%s(v, &s->%s[i], NULL, errp);' % (typename, field['variable'])
            print '    }'
            print '    visit_end_array(v, errp);'
        elif field.has_key('default'):
            if is_save:
                print '    if (s->%s != %s) {' % (field['variable'], field['default'])
                print '        visit_type_%s(v, &s->%s, "%s", errp);' % (typename, field['variable'], field['variable'])
                print '    }'
            else:
                print '    s->%s = %s;' % (field['variable'], field['default'])
                print '    visit_type_%s(v, &s->%s, "%s", NULL);' % (typename, field['variable'], field['variable'])
        else:
            print '    visit_type_%s(v, &s->%s, "%s", errp);' % (typename, field['variable'], field['variable'])
    print '    visit_end_struct(v, errp);'
    print '}'
    print

if __name__ == '__main__':
    la = LookAhead(skip(lexer(Input(sys.stdin))))

    index = 0
    while True:
        try:
            if choice(la, index, 'typedef'):
                offset, node = parse_typedef(la, index)
            else:
                offset, node = parse_struct(la, index)

            index, _ = expect(la, index + offset, 'operator', ';')
        except StopIteration, e:
            break

        qapi_format(node, True)
        qapi_format(node, False)

    

