import sqlite3
import re

stress_re = re.compile(r'[~`^]')

_create_table_and_index_queries = [
    '''
    CREATE TABLE IF NOT EXISTS"tag_sets" (
        "id"	INTEGER NOT NULL,
        "tag_id"	INTEGER NOT NULL,
        FOREIGN KEY("tag_id") REFERENCES "tags"("id"),
        UNIQUE("id", "tag_id")
    );
    ''',
    '''
    CREATE TABLE IF NOT EXISTS "tags" (
        "id"	INTEGER NOT NULL UNIQUE,
        "tag"	TEXT NOT NULL UNIQUE,
        PRIMARY KEY("id" AUTOINCREMENT)
    );
    ''',
    '''
    CREATE TABLE IF NOT EXISTS "forms" (
        "id"	INTEGER NOT NULL UNIQUE,
        "form"	TEXT NOT NULL,
        "lemma"	TEXT,
        "stressed_form"	TEXT,
        "tag_set_id"	INTEGER NOT NULL,
        PRIMARY KEY("id" AUTOINCREMENT),
        FOREIGN KEY("tag_set_id") REFERENCES "tag_sets"("id")
    );
    ''',
    '''
    CREATE INDEX IF NOT EXISTS "forms_index" ON "forms" (
        "form",
        "lemma",
        "tag_set_id"
    );
    ''',
    '''
    CREATE INDEX IF NOT EXISTS "tag_index" ON "tags" (
        "tag"
    );
    ''',
    '''
    CREATE INDEX IF NOT EXISTS "tag_set_index" ON "tag_sets" (
        "tag_id"
    );
    '''
]

def init(database=":memory:"):
    conn = sqlite3.connect(database)

    c = conn.cursor()

    for q in _create_table_and_index_queries:
        c.execute(q)

    return conn

def convert_jablonskis_to_tag_ids(conn, jablonskis_tags):
    c = conn.cursor()

    for tag in jablonskis_tags:
        try:
            c.execute("INSERT INTO `tags` (`tag`) VALUES (?)", (tag,))
            tag_id = c.lastrowid
        except sqlite3.IntegrityError as e:
            if str(e) == 'UNIQUE constraint failed: tags.tag':
                c.execute("SELECT `id` FROM `tags` WHERE `tag`=?", (tag,))
                tag_id = c.fetchone()[0]
            else:
                raise e
            
        yield tag_id

def find_tag_set_id(conn, tag_id_set):
    c = conn.cursor()
    
    q = 'SELECT tag_sets.id FROM tag_sets JOIN tags ON tags.id=tag_sets.tag_id GROUP BY tag_sets.id HAVING COUNT(*) == %d AND max( CASE WHEN tags.id NOT IN (%s) THEN 1 ELSE 0 END ) = 0' % (len(tag_id_set), ','.join([str(i) for i in tag_id_set]))
    c.execute(q)
    row = c.fetchone()

    return row[0] if row else None

def get_tag_set_id(conn, jablonskis_tags):
    tag_ids = list(convert_jablonskis_to_tag_ids(conn, jablonskis_tags))

    c = conn.cursor()

    tag_set_id = find_tag_set_id(conn, tag_ids)
    if tag_set_id == None:
        c.execute('SELECT MAX(`id`) FROM `tag_sets`')
        row = c.fetchone()
        tag_set_id = 0 if row[0] == None else row[0]+1
    
        for tag_id in tag_ids:
            c.execute("INSERT INTO `tag_sets` (`id`, `tag_id`) VALUES (?,?)", (tag_set_id, tag_id))

    return tag_set_id

def get_tags(conn, tag_set_id):
    c = conn.cursor()

    q = 'SELECT tags.id, tags.tag FROM tag_sets JOIN tags ON tags.id=tag_sets.tag_id WHERE tag_sets=?'
    
    for tag_id, tag in c.execute(q, (tag_set_id,)):
        yield tag_id, tag    

def get(conn, form, tag_set_id, stressed_form=None, lemma=None):
    if stress_re.search(form):
        raise Exception('Word stressed')

    form = form.strip().lower()
    if lemma:
        lemma = lemma.strip().lower()

    result = []
    c = conn.cursor()
    param = (form, stressed_form, tag_set_id)
    q = "SELECT `id`, `stressed_form` FROM `forms` WHERE `form`=? AND `stressed_form`=? AND `tag_set_id`=?"
    for form_id, stressed_form in c.execute(q, param):
        result.append( (form_id, stressed_form) )

    return result

def add(conn, form, stressed_form, jablonskis_tags, lemma=None):
    tag_set_id = get_tag_set_id(conn, jablonskis_tags)
    results = get(conn, form, tag_set_id, stressed_form=stressed_form, lemma=lemma)

    if not results:
        c = conn.cursor()

        form = form.strip().lower()
        stressed_form = stressed_form.strip().lower()
        if lemma:
            lemma = lemma.strip().lower()
            
        param = (form, stressed_form, lemma, tag_set_id)

        c.execute("INSERT INTO `forms` (`form`, `stressed_form`, `lemma`, `tag_set_id`) VALUES (?, ?, ?, ?)", param)
        form_id = c.lastrowid

        return form_id

def update_lemma(conn, form, lemma, stressed_form, jablonskis_tags):
    c = conn.cursor()

    form = form.strip().lower()
    stressed_form = stressed_form.strip().lower()
    if lemma:
        lemma = lemma.strip().lower()
        
    tag_set_id = get_tag_set_id(conn, jablonskis_tags)
    for form_id, _ in get(conn, form, tag_set_id, stressed_form=stressed_form):
        param = (lemma, form_id)
        c.execute("UPDATE `forms` SET `lemma`=?  WHERE `id`=?", param)

stress_chars_re = re.compile(r'[`~^]')
group_chars_re = re.compile(r'[()]')

def stress(conn, form, lemma, jablonskis_tags):
    tag_set_id = get_tag_set_id(conn, jablonskis_tags)
    stressed_form = None
    for res in get(conn, form, tag_set_id, lemma=lemma):
        stressed_form = res[1] if res else None
        break

    if stressed_form:
        if not group_chars_re.match(form):
            form_out = str(form)
            group_text_re = stress_chars_re.sub('()', stressed_form)
            stress_locations = re.search(group_text_re, form, flags=re.IGNORECASE)
            for m, reg in reversed(list(zip(stress_chars_re.finditer(stressed_form), stress_locations.regs[1:]))):
                form_out = form_out[:reg[0]] + m.group(0) + form_out[reg[0]:]

            return form_out

def get_multi_pos(conn):
    q = 'SELECT forms.id,form,lemma,stressed_form,tag_set_id FROM forms WHERE form in (SELECT form FROM forms GROUP BY form, tag_set_id HAVING count(*) > 1) ORDER BY form'

    c = conn.cursor()
    for forms_id,form,lemma,stressed_form,tag_set_id in c.execut(q): 
        pos = ''.join(get_tags(conn, tag_set_id))
        yield forms_id,form,lemma,stressed_form,pos

def get_homographs(conn):
    q = '''
    SELECT id,form,lemma,stressed_form,tag_set_id FROM forms
    WHERE form in (SELECT DISTINCT form FROM forms GROUP BY form, tag_set_id HAVING count(DISTINCT stressed_form) > 1 AND form <> stressed_form)
    '''

    c = conn.cursor()
    for forms_id,form,lemma,stressed_form,tag_set_id in c.execut(q): 
        pos = ''.join(get_tags(conn, tag_set_id))
        yield forms_id,form,lemma,stressed_form,pos