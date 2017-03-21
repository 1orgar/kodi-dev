# -*- coding: utf-8 -*-

import re


class AnimeDB:
    def __init__(self, data_file):
        from debug import CDebug
        self.log = CDebug(prefix='DB')
        del CDebug
        self.log('Loading database')
        import sqlite3 as db
        self.c = db.connect(database=data_file)
        del db
        self.cu = self.c.cursor()
        self._create_tables()

    def end(self):
        self.c.close()

    def _create_tables(self):
        self.cu.execute('SELECT COUNT(1) FROM sqlite_master WHERE type=\'table\' AND name=\'viewed_episodes\'')
        self.c.commit()
        if self.cu.fetchone()[0] == 0:
            self.cu.execute('CREATE TABLE viewed_episodes(anime_id INT NOT NULL, file TEXT NOT NULL, episode INT DEFAULT 0, added DEFAULT CURRENT_TIMESTAMP, CONSTRAINT pk PRIMARY KEY (anime_id, file, episode))')
            self.c.commit()
            self.cu.execute('CREATE INDEX fe_i ON viewed_episodes (file, episode)')
            self.c.commit()
            self.cu.execute('CREATE INDEX f_i ON viewed_episodes (file)')
            self.c.commit()
            self.cu.execute('CREATE INDEX t_i ON viewed_episodes (added)')
            self.c.commit()
            self.log('Creating table viewed_episodes')
        self.cu.execute('SELECT COUNT(1) FROM sqlite_master WHERE type=\'table\' AND name=\'anime_db\'')
        self.c.commit()
        if self.cu.fetchone()[0] == 0:
            self.cu.execute('CREATE TABLE anime_db(anime_id INTEGER NOT NULL PRIMARY KEY, title_ru TEXT, title_orig TEXT, year INTEGER, genre TEXT, director TEXT, writer TEXT, plot TEXT, dubbing TEXT, translation TEXT, sound TEXT, rating INTEGER)')
            self.c.commit()
            self.cu.execute('CREATE UNIQUE INDEX i_i ON anime_db (anime_id)')
            self.c.commit()
            self.log('Creating table anime_db')
        self.cu.execute('SELECT COUNT(1) FROM sqlite_master WHERE type=\'table\' AND name=\'search_list\'')
        self.c.commit()
        if self.cu.fetchone()[0] == 0:
            self.cu.execute('CREATE TABLE search_list(search TEXT PRIMARY KEY NOT NULL)')
            self.c.commit()
            self.log('Creating table search_list')

    def searches_add(self, s):
        self.cu.execute('INSERT OR REPLACE INTO search_list (search) VALUES (?)', (s.decode('utf-8'),))
        self.c.commit()

    def searches_get(self):
        res = list()
        self.cu.execute('SELECT search FROM search_list')
        self.c.commit()
        for v in self.cu.fetchall():
            res.append(v[0].encode('utf-8'))
        return res

    def viewed_episode_add(self, anime_id, file_name):
        try:
            ep = int(re.search(r'\[\d+\]', file_name).group()[1:-1])
        except:
            ep = 0
        self.cu.execute('INSERT OR REPLACE INTO viewed_episodes (anime_id, file, episode) VALUES (?,?,?)', (int(anime_id), file_name, ep))
        self.c.commit()

    def is_episode_viewed(self, anime_id, file_name):
        try:
            ep = int(re.search(r'\[\d+\]', file_name).group()[1:-1])
            self.cu.execute('SELECT COUNT(1) FROM viewed_episodes WHERE anime_id=? AND episode=?', (anime_id, ep))
        except:
            self.cu.execute('SELECT COUNT(1) FROM viewed_episodes WHERE file=?', (file_name.decode('utf-8'),))
        self.c.commit()
        return False if self.cu.fetchone()[0] == 0 else True

    def is_anime_in_db(self, anime_id):
        self.cu.execute('SELECT COUNT(1) FROM anime_db WHERE anime_id=?', (anime_id,))
        self.c.commit()
        return False if self.cu.fetchone()[0] == 0 else True

    def add_anime(self, anime_id, title, year=0, genre='', director='', writer='', plot='', dubbing='', translation='', sound='', rating=0):
        stitle = self.split_title(title)
        self.cu.execute('INSERT INTO anime_db (anime_id, title_ru, title_orig, year, genre, director, writer, plot, dubbing, translation, sound, rating) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                        (anime_id, stitle[1], stitle[2], int(year), genre, director, writer, plot, dubbing, translation, sound, int(rating)))
        self.c.commit()

    def get_anime(self, anime_id):
        self.cu.execute('SELECT year, genre, director, writer, plot, dubbing, translation, sound, rating FROM anime_db WHERE anime_id=?', (anime_id,))
        self.c.commit()
        return self.cu.fetchone()

    def get_anime_title(self, anime_id):
        self.cu.execute('SELECT title_ru, title_orig FROM anime_db WHERE anime_id=?', (anime_id,))
        self.c.commit()
        res = self.cu.fetchone()
        return res[0], res[1]

    def update_rating(self, anime_id, rating):
        self.cu.execute('UPDATE anime_db SET rating=? WHERE anime_id=?', (rating, anime_id))
        self.c.commit()

    def get_genre_list(self, ordered=False):
        gl = ['авиация','сёнэн', 'романтика', 'драма', 'комедия', 'этти', 'меха', 'фантастика', 'фэнтези', 'повседневность',
              'школа', 'война', 'сёдзё', 'детектив', 'ужасы', 'история', 'триллер', 'приключения', 'киберпанк', 'мистика',
              'музыкальный', 'спорт', 'пародия', 'для детей', 'махо-сёдзё', 'сказка', 'сёдзё-ай', 'сёнэн-ай', 'боевые искусства', 'самурайский боевик']
        gl_excl = ['', '18+', 'j-pop', 'j-rock', 'дрaмa', 'ромaнтикa', 'без жанра']
        self.cu.execute('SELECT DISTINCT genre FROM anime_db')
        self.c.commit()
        for i in self.cu.fetchall():
            for j in i[0].split(', '):
                j = j.lower().strip().encode('utf-8')
                if not j in gl and not j in gl_excl:
                    gl.append(j)
        if ordered:
            gl.sort()
        return gl

    def get_dubbers_list(self):
        dl = ['Ancord', 'Cuba77', 'Nika Lenina', 'Онитян', 'Inspector_Gadjet', 'OSLIKt', 'Trina_D', 'Shina', 'Lord Alukart',
              'MCShaman', 'Стефан', 'Keita', 'Holly', 'Lonely Dragon', 'Tinko', 'Tori', 'Oriko', 'Trouble', 'JAM', 'BalFor',
              'Симбад', 'FruKt', 'Kiara_Laine', 'Гамлетка Цезаревна', 'NASTR']
        return dl

    def get_history(self, count=20):
        self.cu.execute('SELECT DISTINCT anime_id FROM viewed_episodes ORDER BY added DESC LIMIT ?', (count,))
        self.c.commit()
        res = list()
        for i in self.cu.fetchall():
            res.append(i[0])
        return res


    def split_title(self, title):
        v = title.split(' / ', 1)
        if len(v) == 1:
            v = title.split('  ', 1)
        try:
            part_pos = re.search('\s\[.+\]', v[len(v) - 1]).start()
            v.insert(0, v[len(v) - 1][part_pos + 1:])
            v[len(v) - 1] = v[len(v) - 1][:part_pos]
        except:
            v.insert(0, '')
        if len(v) == 2:
            v.append('')
        return v

    def get_ep_from_filename(self, file_name):
        return None

