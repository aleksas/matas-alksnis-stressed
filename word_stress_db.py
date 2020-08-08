import sqlite3

_create_table_queries = [
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
        "lemma"	TEXT NOT NULL,
        "stressed_form"	TEXT,
        "tag_set_id"	INTEGER NOT NULL,
        PRIMARY KEY("id" AUTOINCREMENT),
        FOREIGN KEY("tag_set_id") REFERENCES "tag_sets"("id")
    );
    '''
]

def init(database=":memory:"):
    conn = sqlite3.connect(database)

    c = conn.cursor()

    for q in _create_table_queries:
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

def get_tag_set_id(conn, tag_id_set):
    c = conn.cursor()
    
    q = 'SELECT tag_sets.id FROM tag_sets JOIN tags ON tags.id=tag_sets.tag_id GROUP BY tag_sets.id HAVING COUNT(*) == %d AND max( CASE WHEN tags.id NOT IN (%s) THEN 1 ELSE 0 END ) = 0' % (len(tag_id_set), ','.join([str(i) for i in tag_id_set]))
    c.execute(q)
    row = c.fetchone()

    return row[0] if row else None

def add_tag_set(conn, jablonskis_tags):
    tag_ids = list(convert_jablonskis_to_tag_ids(conn, jablonskis_tags))

    c = conn.cursor()

    tag_set_id = get_tag_set_id(conn, tag_ids)
    if tag_set_id == None:
        c.execute('SELECT MAX(`id`) FROM `tag_sets`')
        row = c.fetchone()
        tag_set_id = 0 if row[0] == None else row[0]+1
    
        for tag_id in tag_ids:
            c.execute("INSERT INTO `tag_sets` (`id`, `tag_id`) VALUES (?,?)", (tag_set_id, tag_id))

    return tag_set_id

def add(conn, form, stressed_form, lemma, jablonskis_tags):
    tag_set_id = add_tag_set(conn, jablonskis_tags)

    form = form.strip().lower()
    stressed_form = stressed_form.strip().lower()
    lemma = lemma.strip().lower()

    c = conn.cursor()
    param = (form, stressed_form, lemma, tag_set_id)

    c.execute("SELECT `id` FROM `forms` WHERE `form`=? AND `stressed_form`=? AND `lemma`=? AND `tag_set_id`=?", param)
    row = c.fetchone()
    if row:
        form_id = row[0]
    else:
        c.execute("INSERT INTO `forms` (`form`, `stressed_form`, `lemma`, `tag_set_id`) VALUES (?, ?, ?, ?)", param)
        form_id = c.lastrowid

    return form_id
    