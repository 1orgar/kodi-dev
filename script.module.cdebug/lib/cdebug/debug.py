#CDebug v 1.5

import xbmc
import sys
import os
from datetime import datetime

def fs_enc(path):
    sys_enc = sys.getfilesystemencoding() if sys.getfilesystemencoding() else 'utf-8'
    return path.decode('utf-8').encode(sys_enc)


class CDebug:
    class __CDebug:
        def __init__(self, filename):
            self._filename = os.path.join(fs_enc(xbmc.translatePath('special://home')), os.path.basename(filename))
            self._enabled = False
            self._max_size = 2 * 1024 * 1024
            self._max_len = 150

        def out(self, s):
            log = open(self._filename, 'a')
            if len(s) > self._max_len:
                s = '%s...%s' % (s[:self._max_len / 2], s[-(self._max_len / 2):])
            try:
                log.write('%s: %s\r\n' % (str(datetime.now().strftime('%H:%M:%S.%f')[:-3]), str(s)))
            except Exception, e:
                log.write('Logfile error: %s' % e)
            log.close()
            if os.path.getsize(self._filename) > self._max_size:
                self._rotate()

        def _rotate(self):
            lastlog = self._filename + '.last'
            if os.path.exists(lastlog):
                os.remove(lastlog)
            os.rename(self._filename, lastlog)
            self.out('New log file created, last log saved as ' + lastlog)

    inst = None
    def __init__(self, filename=None, prefix=None):
        self._prefix = prefix
        if not CDebug.inst:
            if filename is None:
                raise Exception('No debug filename specified')
            CDebug.inst = CDebug.__CDebug(filename)

    def __call__(self, o):
        if self._prefix is not None:
            o = '[%s] %s' % (self._prefix, o)
        CDebug.inst.out(o)

    @staticmethod
    def log(o):
        if CDebug.inst:
            CDebug.inst.out(o)

    @staticmethod
    def dump(obj):
        newobj = obj
        if '__dict__' in dir(obj):
            newobj = obj.__dict__
            if ' object at ' in str(obj) and not newobj.has_key('__type__'):
                newobj['__type__'] = str(obj)
            for attr in newobj:
                newobj[attr] = CDebug.dump(newobj[attr])
        return newobj

    def enabled(self, b=False):
        CDebug.inst.enabled = b


