# -*- coding: utf-8 -*-

import os
import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import urlparse
import urllib
import hashlib
from cdebug import CDebug

WIDE_LIST_VIEW = {'skin.confluence': 51, 'skin.estouchy': 550, 'skin.estuary': 55, 'skin.xperience1080': 50,
                  'skin.re-touched': 50, 'skin.unity': 51, 'skin.transparency': 52, 'skin.aeon.nox.5': 55}

def fs_enc(path):
    sys_enc = sys.getfilesystemencoding() if sys.getfilesystemencoding() else 'utf-8'
    return path.decode('utf-8').encode(sys_enc)

def fs_dec(path):
    sys_enc = sys.getfilesystemencoding() if sys.getfilesystemencoding() else 'utf-8'
    return path.decode(sys_enc).encode('utf-8')

def mkreq(params):
    return '%s?%s' % (sys.argv[0], urllib.urlencode(params))

class Tfp(object):
    __plugin__ = sys.modules["__main__"].__plugin__
    __settings__ = sys.modules["__main__"].__settings__
    __root__ = sys.modules["__main__"].__root__
    __handle__ = int(sys.argv[1])
    icon = os.path.join(__root__, 'icon.png')

    def __init__(self):
        self.log = CDebug(filename='Tfp.log', prefix='TFP')
        self.log('Initialization')
        self.addon_data_dir = fs_enc(xbmc.translatePath(Tfp.__settings__.getAddonInfo('profile')))
        self.stream_dir = os.path.join(self.addon_data_dir, 'streams')
        if not os.path.exists(self.addon_data_dir):
            self.log('Creating folder: ' + self.addon_data_dir)
            os.makedirs(self.addon_data_dir)
        if not os.path.exists(self.stream_dir):
            self.log('Creating folder: ' + self.stream_dir)
            os.makedirs(self.stream_dir)
        self.params = dict()

        self.params = {'mode': 'main', 'param': '', 'torrent_file': ''}
        args = urlparse.parse_qs(sys.argv[2][1:])
        for a in args:
            self.params[a] = args[a][0]

        self.log('Loading database')
        import sqlite3 as db
        db_path = os.path.join(self.addon_data_dir, 'views.db')
        self.c = db.connect(database=db_path)
        self.cu = self.c.cursor()
        self._create_tables()
        del db
        self.cont_play = Tfp.__settings__.getSetting('cont_play') == 'true'
        if Tfp.__settings__.getSetting("engine") != '':
            Tfp.__settings__.setSetting("engine", '')
            self.params['mode'] = 'p2psettings'

    def execute(self):
        self.log('Mode: %s' % self.params['mode'])
        if self.params['mode'] == 'main':
            self._open_torrent_dialog()
        elif self.params['mode'] == 'play':
            self._play_file_index(self.params['torrent_file'], int(self.params['index']))
        elif self.params['mode'] == 'cplay':
            self._continious_play(self.params['torrent_file'], self.params['indexes'])
        elif self.params['mode'] == 'p2psettings':
            import xbmcaddon
            xbmcaddon.Addon(id='script.module.tengine').openSettings()
            Tfp.__settings__.openSettings()
        elif self.params['mode'] == 'ml':
            self._add_to_ml()
        self.c.close()

    def _create_tables(self):
        self.cu.execute('SELECT COUNT(1) FROM sqlite_master WHERE type=\'table\' AND name=\'viewed\'')
        self.c.commit()
        if self.cu.fetchone()[0] == 0:
            self.log('Creating database tables')
            self.cu.execute('CREATE TABLE IF NOT EXISTS viewed(file TEXT NOT NULL PRIMARY KEY)')
            self.c.commit()
            self.cu.execute('CREATE INDEX f_i ON viewed (file)')
            self.c.commit()

    def _show_message(self, h, m):
        xbmc.executebuiltin('XBMC.Notification("%s", "%s", %s, "%s")' % (h, m, 3000, ''))

    def _add_to_ml(self):
        file_name = self.params['torrent_file']
        self.log('ML: Params: %s' % CDebug.dump(self.params))
        if not xbmcvfs.exists(file_name):
            self.log('Torrent file not found: %s' % file_name)
            raise Exception('Torrent file not found: %s' % file_name)
        fl = xbmcvfs.File(file_name, 'rb')
        content = fl.read()
        fl.close()
        h_file_name = os.path.join(self.stream_dir, '%s.torrent' % hashlib.sha1(content).hexdigest())
        s_file_name = os.path.join(self.stream_dir, '%s.strm' % hashlib.sha1(self.params['title']).hexdigest())
        self.log('Torrent file: %s' % h_file_name)
        self.log('Stream file: %s' % s_file_name)
        if not xbmcvfs.exists(h_file_name):
            fl = xbmcvfs.File(h_file_name, 'wb')
            fl.write(content)
            fl.close()
        if not xbmcvfs.exists(s_file_name):
            fl = xbmcvfs.File(s_file_name, 'w')
            fl.write(mkreq({'mode': 'play', 'torrent_file': h_file_name, 'index': int(self.params['index'])}))
            fl.close()

    def _consist_check(self):
        #if xbmc.getInfoLabel('Container.PluginName') != 'plugin.video.torrent.file.player':
        #    self.log('External playback calls denied')
        #    return False
        self.log('External playback call from: %s' % xbmc.getInfoLabel('Container.Content'))
        return True

    def _open_torrent_dialog(self):
        if self.params['torrent_file'] == '':
            xbmcplugin.endOfDirectory(handle=self.__handle__, succeeded=False, updateListing=True, cacheToDisc=False)
            open_dialog = xbmcgui.Dialog()
            torrent_file = open_dialog.browse(1, 'Выберите .torrent файл.', 'video', '.torrent')
            if torrent_file:
                xbmc.executebuiltin('XBMC.Container.Update("plugin://plugin.video.torrent.file.player?'
                                    'mode=main&torrent_file=%s", replace)' % urllib.quote_plus(torrent_file))
            else:
                xbmc.executebuiltin('XBMC.Container.Update("addons://sources/video/", replace)')
        else:
            self._get_contents(torrent_file=self.params['torrent_file'])

    def _get_contents(self, torrent_file):
        from tengine import TEngine
        self.log('Loading torrent file: %s' % torrent_file)
        torrent = TEngine(file_name=torrent_file)
        del TEngine
        if len(torrent.enumerate_files()) == 1:
            self.cont_play = False
        for file in sorted(torrent.enumerate_files(), key=lambda k: k['file']):
            info = dict()
            li = xbmcgui.ListItem(urllib.unquote(file['file']), iconImage='DefaultVideo.png',
                                  thumbnailImage='DefaultVideo.png')
            li.setProperty('IsPlayable', 'false' if self.cont_play else 'true')
            info['size'] = int(file['size'])
            li.setInfo(type='video', infoLabels=info)
            if self.cont_play:
                idx_list = ''
                idx_start = False
                for f in sorted(torrent.enumerate_files(), key=lambda k: k['file']):
                    if file['index'] == f['index']:
                        idx_start = True
                    if idx_start:
                        idx_list += '%d-' % f['index']
                url = mkreq({'mode': 'cplay', 'torrent_file': torrent_file, 'indexes': idx_list[:-1]})
            else:
                url = mkreq({'mode': 'play', 'torrent_file': torrent_file, 'index': int(file['index'])})
            self.cu.execute('SELECT COUNT(1) FROM viewed WHERE file=?', (file['file'].decode('utf-8'),))
            self.c.commit()
            if self.cu.fetchone()[0] == 1:
                li.select(True)
            context_menu = [('Добавить в медиатеку', 'RunPlugin(%s)' %
                                 mkreq({'mode': 'ml', 'param': 'add', 'torrent_file': torrent_file,
                                        'index': int(file['index']), 'title': urllib.unquote(file['file'])}))]
            li.addContextMenuItems(context_menu)
            xbmcplugin.addDirectoryItem(handle=self.__handle__, url=url, listitem=li, isFolder=False)
        xbmcplugin.setContent(handle=self.__handle__, content='Movies')
        xbmc.executebuiltin('Container.SetViewMode(%d)' % WIDE_LIST_VIEW.get(xbmc.getSkinDir(), 50))
        xbmcplugin.endOfDirectory(handle=self.__handle__, updateListing=True, cacheToDisc=True)
        torrent.end()

    def _play_file_index(self, torrent_file, index, resolved_url=True):
        if not self._consist_check():
            return
        from tengine import TEngine
        torrent = TEngine(file_name=torrent_file)
        del TEngine
        title =''
        for f in torrent.enumerate_files():
            if f['index'] == index:
                title = f['file']
                break
        self.log('Starting playback: %s' % title)
        if not torrent.play(index, title, 'DefaultVideo.png', self.icon, resolved_url):
            xbmc.executebuiltin('XBMC.Notification("Torrent File Player", "Playback Error", 2000, "")')
        else:
            self.cu.execute('INSERT OR REPLACE INTO viewed (file) VALUES (?)', (title.decode('utf-8'),))
            self.c.commit()
        torrent.end()
        return torrent.playback_ended

    def _continious_play(self, torrent_file, indexes):
        idx = indexes.split('-')
        for i in idx:
            if not self._play_file_index(torrent_file, int(i), False):
                break
