# -*- coding: utf-8 -*-
# version 1.3

import sys
import xbmc
import xbmcvfs
import xbmcgui
import xbmcplugin
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

    def __init__(self, file_name=None, engine_type=0, save_path=None, keep_files=False, resume_saved=False):
        if engine_type == TEngine.ACESTREAM:
            from ASCore import TSengine
            self.engine = TSengine()
            del TSengine
            #self.engine.set_saving_settings(keep_files, save_path, resume_saved)
        elif engine_type == TEngine.PY2HTTP or engine_type == TEngine.T2HTTP:
            try:
                from python_libtorrent import get_libtorrent
                libtorrent = get_libtorrent()
            except:
                import libtorrent
            self.lt = libtorrent
            del libtorrent
            self.resume_saved = resume_saved if keep_files else False
            self.keep_files = keep_files
            self.torrent_file_dir = os.path.join(xbmc.translatePath('special://temp/'), 'tengine')
            self.torrent_store_dir = save_path if save_path else os.path.join(xbmc.translatePath('special://temp/'), 'tengine')
            if not xbmcvfs.exists(self.torrent_file_dir):
                xbmcvfs.mkdirs(self.torrent_file_dir)
            self.engine = None
            self.player = None
        self.torrent_file = file_name
        self.status = ''
        self.en_type = engine_type
        self.files = list()
        self.re_path2fl = re.compile(r'(^.+\\)|(^.+\/)')
        self.re_fl_ext = re.compile(r'.+(\..+)$')
        if file_name:
            self.load_file(file_name)

    def __del__(self):
        self.end()

    def cleanup(self):
        import shutil
        try:
            for root, dirs, files in os.walk(fs_enc(self.torrent_file_dir)):
                for f in files:
                    os.unlink(os.path.join(root, f))
                for d in dirs:
                    shutil.rmtree(os.path.join(root, d))
        except:
            pass
        finally:
            del shutil



    def load_file(self, file_name):
        if xbmcvfs.exists(file_name):
            self.torrent_file = file_name
            fl = xbmcvfs.File(file_name, 'rb')
            content = fl.read()
            fl.close()
            if self.en_type == TEngine.ACESTREAM:
                self.status = self.engine.load_torrent(base64.b64encode(content), 'RAW')
                if self.status:
                    for k, v in self.engine.files.iteritems():
                        self.files.append({"index": int(v), "file": k, 'size': 0})
            elif self.en_type == TEngine.PY2HTTP or self.en_type == TEngine.T2HTTP:
                e = self.lt.bdecode(content)
                fls = self.lt.torrent_info(e)
                for c_id, c_fl in enumerate(fls.files()):
                    if self.re_fl_ext.search(c_fl.path):
                        if self.re_fl_ext.search(c_fl.path).group(1)[1:] in TEngine.VIDEO_FILE_EXT:
                            self.files.append({'index': int(c_id), 'file': self.re_path2fl.sub('', c_fl.path),
                                               'size': c_fl.size})
                self.torrent_file = os.path.join(self.torrent_file_dir, self.re_path2fl.sub('', file_name))
                fl_s = xbmcvfs.File(file_name, 'rb')
                fl_d = xbmcvfs.File(self.torrent_file, 'wb')
                fl_d.write(fl_s.read())
                fl_d.close()
                fl_s.close()
                dht_routers = ["router.bittorrent.com:6881", "router.utorrent.com:6881"]
                user_agent = 'uTorrent/2200(24683)'
                if self.en_type == TEngine.PY2HTTP:
                    from pyrrent2http import Engine
                else:
                    from torrent2http import Engine
                self.engine = Engine(uri=urlparse.urljoin('file:', urllib.pathname2url(self.torrent_file)),
                                     download_path=self.torrent_store_dir, connections_limit=None, encryption=1,
                                     download_kbps=0, upload_kbps=0, keep_complete=self.keep_files,
                                     keep_incomplete=self.keep_files, keep_files=self.keep_files,
                                     dht_routers=dht_routers, use_random_port=True, listen_port=6881, user_agent=user_agent,
                                     resume_file=None if not self.keep_files else self.torrent_file + '.resume_data')
                del Engine
                self.status = 'Ok'

    def play(self, index, title, icon='', image='', use_resolved_url=False):
        if self.status == 'Ok':
            if self.en_type == TEngine.ACESTREAM:
                return self.engine.play_url_ind(int(index), title, icon, image, use_resolved_url)
            elif self.en_type == TEngine.PY2HTTP or self.en_type == TEngine.T2HTTP:
                self.player = tpy2httpPlayer(engine=self.engine, en_type=self.en_type, index=index, title=title,
                                             icon=icon, image=image, use_resolved_url=use_resolved_url,
                                             resume_saved=self.resume_saved)
                while self.player.active:
                    xbmc.sleep(300)
                    self.player.loop()
                    if xbmc.abortRequested:
                        break
                return not self.player.err
        else:
            return False

    def enumerate_files(self):
        return self.files

    def set_resume_saved(self, rs):
        if self.en_type == TEngine.ACESTREAM:
            self.engine.resume_saved = rs
        elif self.en_type == TEngine.PY2HTTP or self.en_type == TEngine.T2HTTP:
            self.resume_saved = rs

    def set_temporary_folder(self, tf):
        if xbmcvfs.exists(tf):
            self.torrent_file_dir = tf
            self.torrent_store_dir = tf



    def is_file_playback_ended(self):
        if self.en_type == TEngine.ACESTREAM:
            if not self.engine.player:
                return False
            return self.engine.player.ended
        elif self.en_type == TEngine.PY2HTTP or self.en_type == TEngine.T2HTTP:
            if not self.player:
                return False
            return self.player.ended

    def end(self):
        if self.en_type == TEngine.ACESTREAM:
            self.engine.end()
        elif self.en_type == TEngine.PY2HTTP or self.en_type == TEngine.T2HTTP:
            try:
                self.engine.close()
            except:
                pass


class tpy2httpPlayer(xbmc.Player):
    def __init__(self, engine, en_type, index, title, icon, image, use_resolved_url, resume_saved):
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
        except:
            self.err = True
            self.active = False
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
        if status.state == self.state.FINISHED and self.isPlaying() and self.resume_saved:
            xbmc.sleep(2000)
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
                self.ov_label.setLabel('Загрузка завершена.\n[B]Пауза.[/B]')

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


def debug(s):
    from datetime import datetime
    log = open(os.path.join(fs_enc(xbmc.translatePath('special://home')), 'TENGINE.log'), 'a')
    log.write('%s: %s\r\n' % (str(datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]), str(s)))
    log.close()