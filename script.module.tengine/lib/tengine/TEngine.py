# -*- coding: utf-8 -*-
# version 1.4.6

import sys
import xbmc
import xbmcvfs
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib
import base64
import re
import os
import urlparse


class TEngine:
    ACESTREAM = 0
    PY2HTTP = 1
    T2HTTP = 2
    VIDEO_FILE_EXT = ['3gp', 'avi', 'mkv', 'mp4', 'mov', 'wmv', 'm2ts', 'ts', 'divx', 'ogm', 'm4v',
                      'flv', 'm2v', 'mpeg', 'mpg', 'mts', 'vob', 'bdmv']
    PRELOAD_SIZE_MIN = 20 * 1024 * 1024
    PRELOAD_SIZE_MAX = 200 * 1024 * 1024
    PRELOAD_SIZE_FACTOR = 3

    __settings__ = xbmcaddon.Addon(id='script.module.tengine')

    def __init__(self, **kwargs):
        from debug import CDebug
        self.log = CDebug(filename='TEngine.log', prefix='TENGINE')
        del CDebug
        self.log('Initialization')

        self._file_name = None
        self._engine = None
        self._player = None
        self._status = ''
        self._files = list()
        self._re_path2fl = re.compile(r'(^.+\\)|(^.+\/)')
        self._re_fl_ext = re.compile(r'.+(\..+)$')

        self._engine_type = int(TEngine.__settings__.getSetting('engine'))
        self._temp_path = TEngine.__settings__.getSetting('temp_path') if TEngine.__settings__.getSetting('use_custom_temp_path') == 'true' else None
        self._save_path = TEngine.__settings__.getSetting('save_path') if TEngine.__settings__.getSetting('save_files') == 'true' else None
        self._resume_saved = TEngine.__settings__.getSetting('switch_playback') == 'true'

        for k in ('file_name', 'engine_type', 'save_path', 'resume_saved', 'temp_path'):
            if k in kwargs:
                setattr(self, '_' + k, kwargs[k])

        if self._engine_type != TEngine.ACESTREAM and self._engine_type != TEngine.PY2HTTP and self._engine_type != TEngine.T2HTTP:
            self._engine_type = TEngine.ACESTREAM
            self.log('Using AceStream as default engine')

        if self._temp_path:
            if not os.path.exists(fs_enc(self._temp_path)):
                self._temp_path = None
                self.log('Temp folder is not found using system default')
            elif not self._write_check(fs_enc(self._temp_path)):
                self._temp_path = None
                self.log('Temp folder is write protected using system default')
        if not self._temp_path:
            self._temp_path = os.path.join(xbmc.translatePath('special://temp/'), 'tengine')
            if not os.path.exists(fs_enc(self._temp_path)):
                os.makedirs(fs_enc(self._temp_path))
                self.log('Creating folder: ' + self._temp_path)
            if not self._write_check(fs_enc(self._temp_path)):
                raise Exception('System temp path is unavailible: %s' % self._temp_path)
        self.log('Using temp folder: %s' % self._temp_path)

        if self._save_path:
            if not os.path.exists(fs_enc(self._save_path)):
                self._save_path = None
                self.log('Storage folder is not found, streaming only')
            elif not self._write_check(fs_enc(self._save_path)):
                self._save_path = None
                self.log('Storage folder is write protected, streaming only')
            else:
                self.log('Using storage folder: %s' % self._save_path)
        if not self._save_path:
            self._resume_saved = False

        if self._engine_type == TEngine.ACESTREAM:
            from ASCore import TSengine
            self._engine = TSengine()
            del TSengine
        elif self._engine_type == TEngine.PY2HTTP or self._engine_type == TEngine.T2HTTP:
            try:
                from python_libtorrent import get_libtorrent
                libtorrent = get_libtorrent()
            except:
                import libtorrent
            self._lt = libtorrent
            del libtorrent
        if self._file_name:
            self.load_file(self._file_name)

    def __del__(self):
        self.log('Shutting down')
        self.end()

    def _write_check(self, folder):
        try:
            test_file = os.path.join(folder, '.test')
            fl = open(test_file, 'w')
            fl.close()
            os.remove(test_file)
            return True
        except IOError:
            return False

    def cleanup(self):
        import shutil
        try:
            self.log('Cleaning up')
            for root, dirs, files in os.walk(fs_enc(self._temp_path)):
                for f in files:
                    os.unlink(os.path.join(root, f))
                for d in dirs:
                    shutil.rmtree(os.path.join(root, d))
        except:
            pass
        finally:
            del shutil



    def load_file(self, file_name):
        if not xbmcvfs.exists(file_name):
            self.log('Torrent file not found: %s' % file_name)
            raise Exception('Torrent file not found: %s' % file_name)
        self._file_name = file_name
        fl = xbmcvfs.File(self._file_name, 'rb')
        content = fl.read()
        fl.close()
        if self._engine_type == TEngine.ACESTREAM:
            self._status = self._engine.load_torrent(base64.b64encode(content), 'RAW')
            if self._status:
                for k, v in self._engine.files.iteritems():
                    self._files.append({"index": int(v), "file": k, 'size': 0})
        elif self._engine_type == TEngine.PY2HTTP or self._engine_type == TEngine.T2HTTP:
            fls = self._lt.torrent_info(self._lt.bdecode(content))
            for c_id, c_fl in enumerate(fls.files()):
                if self._re_fl_ext.search(c_fl.path):
                    if self._re_fl_ext.search(c_fl.path).group(1)[1:] in TEngine.VIDEO_FILE_EXT:
                        self._files.append({'index': int(c_id), 'file': self._re_path2fl.sub('', c_fl.path),
                                           'size': c_fl.size})
            torrent_file = os.path.join(self._temp_path, self._re_path2fl.sub('', self._file_name))
            if self._file_name != torrent_file:
                fl_s = xbmcvfs.File(self._file_name, 'rb')
                fl_d = xbmcvfs.File(torrent_file, 'wb')
                fl_d.write(fl_s.read())
                fl_d.close()
                fl_s.close()
            dht_routers = ["router.bittorrent.com:6881", "router.utorrent.com:6881"]
            user_agent = 'uTorrent/2200(24683)'
            keep_files = bool(self._save_path)
            if self._engine_type == TEngine.PY2HTTP:
                from pyrrent2http import Engine
            else:
                from torrent2http import Engine
            self._engine = Engine(uri=urlparse.urljoin('file:', urllib.pathname2url(torrent_file)),
                                 download_path=self._save_path if self._save_path else self._temp_path,
                                  connections_limit=None, encryption=1,
                                 download_kbps=0, upload_kbps=0, keep_complete=keep_files,
                                 keep_incomplete=keep_files, keep_files=keep_files,
                                 dht_routers=dht_routers, use_random_port=True, listen_port=6881, user_agent=user_agent,
                                 resume_file=None if not keep_files else torrent_file + '.resume_data')
            del Engine
            self._status = 'Ok'

    def play(self, index, title, icon='', image='', use_resolved_url=False):
        if self._status == 'Ok':
            if self._engine_type == TEngine.ACESTREAM:
                return self._engine.play_url_ind(int(index), title, icon, image, use_resolved_url)
            elif self._engine_type == TEngine.PY2HTTP or self._engine_type == TEngine.T2HTTP:
                self._player = tpy2httpPlayer(engine=self._engine, en_type=self._engine_type, index=index, title=title,
                                             icon=icon, image=image, use_resolved_url=use_resolved_url,
                                             resume_saved=self._resume_saved)
                while self._player.active:
                    xbmc.sleep(300)
                    self._player.loop()
                    if xbmc.abortRequested:
                        break
                return not self._player.err
        else:
            return False

    def enumerate_files(self):
        return self._files

    def set_resume_saved(self, rs):
        if self._engine_type == TEngine.ACESTREAM:
            self._engine_type.resume_saved = rs
        elif self._engine_type == TEngine.PY2HTTP or self._engine_type == TEngine.T2HTTP:
            self.resume_saved = rs

    def is_file_playback_ended(self):
        if self._engine_type == TEngine.ACESTREAM:
            if not self._engine.player:
                return False
            return self._engine.player.ended
        elif self._engine_type == TEngine.PY2HTTP or self._engine_type == TEngine.T2HTTP:
            if not self._player:
                return False
            return self._player.ended

    def end(self):
        if self._engine_type == TEngine.ACESTREAM:
            self._engine.end()
        elif self._engine_type == TEngine.PY2HTTP or self._engine_type == TEngine.T2HTTP:
            try:
                self._engine.close()
            except:
                pass


class tpy2httpPlayer(xbmc.Player):
    def __init__(self, engine, en_type, index, title, icon, image, use_resolved_url, resume_saved):
        from debug import CDebug
        self.log = CDebug(prefix='TENGINE_PLYAER')
        del CDebug
        self.title = title
        self.index = index
        self.engine = engine
        self.en_type = en_type
        self.icon = icon
        self.image = image
        self.active = True
        self.paused = False
        self.ov_visible = False
        self.err = False
        self.resume_saved = resume_saved
        self.ended = False
        xbmc.Player.__init__(self)
        ov_image = fs_enc(os.path.join(xbmc.translatePath('special://temp/tengine'), 'bg.png'))
        if not os.path.isfile(ov_image):
            fl = open(ov_image, 'wb')
            fl.write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='))
            fl.close()
        width, height = tpy2httpPlayer.get_skin_resolution()
        w = width
        h = int(0.14 * height)
        x = 0
        y = (height - h) / 2
        self.ov_window = xbmcgui.Window(12005)
        self.ov_label = xbmcgui.ControlLabel(x, y, w, h, '', alignment=6)
        self.ov_background = xbmcgui.ControlImage(x, y, w, h, fs_dec(ov_image))
        self.ov_background.setColorDiffuse("0xD0000000")
        self.ov_visible = False
        try:
            if self.en_type == TEngine.PY2HTTP:
                if not self.engine.started:
                    self.engine.start()
                self.engine.activate_file(index)
            else:
                if not self.engine.started:
                    self.engine.start(index)
        except Exception, e:
            self.err = True
            self.active = False
            self.log('Error: %s' % e)
            return
        progress = xbmcgui.DialogProgress()
        progress.create('Py2http' if self.en_type == TEngine.PY2HTTP else 'torrent2http', 'Инициализация')

        if self.en_type == TEngine.PY2HTTP:
            from pyrrent2http import State
        else:
            from torrent2http import State
        self.state = State
        del State
        while True:
            if xbmc.abortRequested or progress.iscanceled():
                self.active = False
                self.err = True
                return
            xbmc.sleep(300)
            try:
                status = self.engine.status()
                self.engine.check_torrent_error(status)
                file_status = self.engine.file_status(index)
            except:
                self.err = True
                self.active = False
                self.log('Error: %s' % e)
                return
            if not file_status:
                continue
            preload_size = int(float(file_status.size) / 100.0 * TEngine.PRELOAD_SIZE_FACTOR)
            if preload_size < TEngine.PRELOAD_SIZE_MIN: preload_size = TEngine.PRELOAD_SIZE_MIN
            if preload_size > TEngine.PRELOAD_SIZE_MAX: preload_size = TEngine.PRELOAD_SIZE_MAX
            if status.state == self.state.CHECKING_FILES:
                progress.update(int(status.progress * 100), 'Checking preloaded files...', ' ')
            elif status.state == self.state.DOWNLOADING:
                progress.update(int((float(file_status.download) / float(preload_size)) * 100.0),
                                   'Предварительная буферизация', 'Сиды: [B]%d[/B], скорость: [B]%dKb/s[/B]' %
                                   (int(status.num_seeds), int(status.download_rate)))
                if file_status.download >= preload_size:
                    break
            elif status.state in [self.state.FINISHED, self.state.SEEDING]:
                    break
        progress.update(99, 'Запускается воспроизведение', ' ')
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()
        status = self.engine.status()
        file_status = self.engine.file_status(self.index)
        progress.close()
        if status.state == self.state.FINISHED:
            item = xbmcgui.ListItem(title, icon, image, path=file_status.save_path)
            self.active = False
            if use_resolved_url:
                xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)
            else:
                xbmc.Player().play(file_status.save_path, item)
            return
        item = xbmcgui.ListItem(title, icon, image, path=file_status.url)
        if use_resolved_url:
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)
        else:
            self.play(file_status.url, item)

    def loop(self):
        status = self.engine.status()
        file_status = self.engine.file_status(self.index)
        if status.state == self.state.FINISHED and self.isPlaying() and self.resume_saved and not self.paused:
            xbmc.sleep(2000)
            self.log('Resuming playback from local file')
            item = xbmcgui.ListItem(self.title, self.icon, self.image, path=file_status.save_path)
            item.setProperty('StartOffset', str(self.getTime()))
            self.ov_hide()
            xbmc.Player().play(file_status.save_path, item)
            self.active = False
        if self.paused:
            self.ov_update()

    def ov_show(self):
        if not self.ov_visible:
            self.ov_window.addControls([self.ov_background, self.ov_label])
            self.ov_visible = True

    def ov_hide(self):
        if self.ov_visible:
            self.ov_window.removeControls([self.ov_background, self.ov_label])
            self.ov_visible = False

    def ov_update(self):
        if self.ov_visible:
            status = self.engine.status()
            if status.state == self.state.DOWNLOADING:
                file_status = self.engine.file_status(self.index)
                self.ov_label.setLabel('Загрузка файла\nЗавершено: [B]%d%%[/B]\nСиды: [B]%d[/B], скорость: [B]%dKb/s[/B]' %
                                       (int((float(file_status.download) / float(file_status.size)) * 100.0),
                                        int(status.num_seeds), int(status.download_rate)))
            elif status.state == self.state.FINISHED:
                #self.ov_label.setLabel('Загрузка завершена.\n[B]Пауза.[/B]')
                self.ov_hide()

    def onPlayBackStarted(self):
        return

    def onPlayBackEnded(self):
        self.ov_hide()
        self.active = False
        self.ended = True

    def onPlayBackStopped(self):
        self.ov_hide()
        self.active = False

    def onPlayBackPaused(self):
        if self.engine.status().state != self.state.FINISHED:
            self.ov_show()
        self.paused = True

    def onPlayBackResumed(self):
        self.ov_hide()
        self.paused = False

    @staticmethod
    def get_skin_resolution():
        import xml.etree.ElementTree as ET
        skin_path = fs_enc(xbmc.translatePath("special://skin/"))
        tree = ET.parse(os.path.join(skin_path, "addon.xml"))
        res = tree.findall("./extension/res")[0]
        return int(res.attrib["width"]), int(res.attrib["height"])


def fs_enc(path):
    sys_enc = sys.getfilesystemencoding() if sys.getfilesystemencoding() else 'utf-8'
    return path.decode('utf-8').encode(sys_enc)


def fs_dec(path):
    sys_enc = sys.getfilesystemencoding() if sys.getfilesystemencoding() else 'utf-8'
    return path.decode(sys_enc).encode('utf-8')

