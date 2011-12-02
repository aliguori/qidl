import sys, json

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
        elif field.has_key('is_container'):
            if is_save:
                print '    visit_start_list(v, "%s", errp);' % (field['variable'])
                print '    for (GSList *i = v->%s; i; i = i->next) {' % (field['variable'])
                print '        %s *value = i->data;' % (field['type_of'])
                print '        visit_type_%s(v, value, NULL, errp);' % (field['type_of'])
                print '    }'
                print '    visit_end_list(v, errp);'
            else:
                print '    visit_start_list(v, "%s", errp);' % (field['variable'])
                print '    while (visit_has_more(v, errp)) {'
                print '        %s *value = g_malloc0(sizeof(*value));' % (field['type_of'])
                print '        visit_type_%s(v, value, NULL, errp);' % (field['type_of'])
                print '        s->%s = g_slist_append(s->%s, value);' % (field['variable'], field['variable'])
                print '    }'
                print '    visit_end_list(v, errp);'
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
    nodes = json.loads(sys.stdin.read())
    for node in nodes:
        qapi_format(node, True)
        qapi_format(node, False)
