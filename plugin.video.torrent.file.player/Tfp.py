# -*- coding: utf-8 -*-

import os
import sys
import xbmc
import xbmcgui
import xbmcplugin
import urlparse
import urllib

WIDE_LIST_VIEW = {'skin.confluence': 51, 'skin.estouchy': 550, 'skin.estuary': 55, 'skin.xperience1080': 50,
                  'skin.re-touched': 50, 'skin.unity': 51, 'skin.transparency': 52, 'skin.aeon.nox.5': 55}

def fs_enc(path):
    sys_enc = sys.getfilesystemencoding() if sys.getfilesystemencoding() else 'utf-8'
    return path.decode('utf-8').encode(sys_enc)

def debug(s):
    pass
    #from datetime import datetime
    #log = open(os.path.join(fs_enc(xbmc.translatePath('special://home')), 'Tfp.log'), 'a')
    #log.write('%s: %s\r\n' % (str(datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]), str(s)))
    #log.close()

class Tfp(object):
    __plugin__ = sys.modules["__main__"].__plugin__
    __settings__ = sys.modules["__main__"].__settings__
    __root__ = sys.modules["__main__"].__root__
    __handle__ = int(sys.argv[1])
    icon = os.path.join(__root__, 'icon.png')

    def __init__(self):
        self.params = dict()
        args = urlparse.parse_qs(sys.argv[2][1:])
        self.params['mode'] = args.get('mode', ['main'])[0]
        self.params['file'] = args.get('file', [''])[0]
        self.params['torrent_file'] = args.get('torrent_file', [''])[0]
        self.params['index'] = int(args.get('index', [0])[0])
        import sqlite3 as db
        addon_data_path = fs_enc(xbmc.translatePath(self.__settings__.getAddonInfo('profile')))
        if not os.path.exists(addon_data_path):
            os.makedirs(addon_data_path)
        db_path = os.path.join(addon_data_path, 'views.db')
        self.c = db.connect(database=db_path)
        self.cu = self.c.cursor()
        self._create_tables()
        del db
        if self.__settings__.getSetting("use_custom_temp_folder").lower() == 'true':
            self.temp_folder =  self.__settings__.getSetting('custom_temp_folder')
            if not os.path.exists(fs_enc(self.temp_folder)):
                self.temp_folder = None
        else:
            self.temp_folder = None
        self.cont_play = True if self.__settings__.getSetting('cont_play') == 'true' else False
        self.save = True if self.__settings__.getSetting('save') == 'true' else False
        self.folder = self.__settings__.getSetting('folder') if self.save else None
        if self.save and not os.path.exists(fs_enc(self.folder)):
            xbmc.executebuiltin('XBMC.Notification("Torrent File Player", "Saving folder not found", 2000, "")')
            self.__settings__.openSettings()
            sys.exit(0)
        self.resume_saved = True if self.__settings__.getSetting('switch_playback') == 'true' else False
        self.engine = self.__settings__.getSetting('engine')

    def execute(self):
        if self.params['mode'] == 'main':
            self._open_torrent_dialog()
        elif self.params['mode'] == 'play':
            self._play_file_index(self.params['torrent_file'], self.params['file'], self.params['index'])
        elif self.params['mode'] == 'cplay':
            self._continious_play(self.params['torrent_file'], self.params['index'])
        self.c.close()

    def _create_tables(self):
        self.cu.execute('SELECT COUNT(1) FROM sqlite_master WHERE type=\'table\' AND name=\'viewed\'')
        self.c.commit()
        if self.cu.fetchone()[0] == 0:
            self.cu.execute('CREATE TABLE IF NOT EXISTS viewed(file TEXT NOT NULL PRIMARY KEY)')
            self.c.commit()
            self.cu.execute('CREATE INDEX f_i ON viewed (file)')
            self.c.commit()

    def _show_message(self, h, m):
        xbmc.executebuiltin('XBMC.Notification("%s", "%s", %s, "%s")' % (h, m, 3000, ''))

    def _consist_check(self):
        if xbmc.getInfoLabel('Container.PluginName') != 'plugin.video.torrent.file.player':
            return False
        return True

    def _open_torrent_dialog(self):
        if self.params['torrent_file'] == '':
            open_dialog = xbmcgui.Dialog()
            torrent_file = open_dialog.browse(1, 'Выберите .torrent файл.', 'video', '.torrent')
        else:
            torrent_file = self.params['torrent_file']
        if torrent_file:
            self._get_contents(torrent_file=torrent_file)

    def _get_contents(self, torrent_file):
        from tengine import TEngine
        torrent = TEngine(file_name=torrent_file, engine_type=int(self.engine), temp_path=self.temp_folder)
        del TEngine
        if not self.folder or self.cont_play:
            torrent.cleanup()
        if len(torrent.enumerate_files()) == 1:
            self.cont_play = False
        for file in sorted(torrent.enumerate_files(), key=lambda k: k['file']):
            info = dict()
            li = xbmcgui.ListItem(urllib.unquote(file['file']), iconImage='DefaultVideo.png', thumbnailImage='DefaultVideo.png')
            li.setProperty('IsPlayable', 'false' if self.cont_play else 'true')
            info['size'] = int(file['size'])
            li.setInfo(type='video', infoLabels=info)
            if self.cont_play:
                url = '%s?%s' % (sys.argv[0],  urllib.urlencode({'mode': 'cplay', 'torrent_file': torrent_file, 'index': int(file['index'])}))
            else:
                url = '%s?%s' % (sys.argv[0],  urllib.urlencode({'mode': 'play', 'torrent_file': torrent_file, 'file': file['file'], 'index': int(file['index'])}))
            self.cu.execute('SELECT COUNT(1) FROM viewed WHERE file=?', (file['file'].decode('utf-8'),))
            self.c.commit()
            if self.cu.fetchone()[0] == 1:
                li.select(True)
            xbmcplugin.addDirectoryItem(handle=self.__handle__, url=url, listitem=li, isFolder=False)
        xbmcplugin.setContent(handle=self.__handle__, content='Movies')
        xbmc.executebuiltin('Container.SetViewMode(%d)' % WIDE_LIST_VIEW.get(xbmc.getSkinDir(), 50))
        xbmcplugin.endOfDirectory(handle=self.__handle__)
        torrent.end()

    def _play_file_index(self, torrent_file, title, index):
        if not self._consist_check():
            return
        from tengine import TEngine
        torrent = TEngine(file_name=torrent_file, engine_type=int(self.engine), save_path=self.folder, resume_saved=self.resume_saved, temp_path=self.temp_folder)
        del TEngine
        if not torrent.play(index, title, 'DefaultVideo.png', self.icon, True):
            xbmc.executebuiltin('XBMC.Notification("Torrent File Player", "Playback Error", 2000, "")')
        else:
            self.cu.execute('INSERT OR REPLACE INTO viewed (file) VALUES (?)', (title.decode('utf-8'),))
            self.c.commit()
        torrent.end()

    def _continious_play(self, torrent_file, start_index):
        if not self._consist_check():
            return
        from tengine import TEngine
        torrent = TEngine(file_name=torrent_file, engine_type=int(self.engine), temp_path=self.temp_folder)
        del TEngine
        play_start = False
        for file in sorted(torrent.files, key=lambda k: k['file']):
            if start_index == file['index']:
                play_start = True
            if play_start:
                if not torrent.play(file['index'], file['file'], 'DefaultVideo.png', self.icon, False):
                    xbmc.executebuiltin('XBMC.Notification("Torrent File Player", "Playback Error", 2000, "")')
                    break
                else:
                    self.cu.execute('INSERT OR REPLACE INTO viewed (file) VALUES (?)', (file['file'].decode('utf-8'),))
                    self.c.commit()
                if not torrent.is_file_playback_ended():
                    break
        torrent.end()

