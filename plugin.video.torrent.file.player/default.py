# -*- coding: utf-8 -*-

import sys
import gc
import xbmcaddon

__settings__ = xbmcaddon.Addon(id='plugin.video.torrent.file.player')
__plugin__ = __settings__.getAddonInfo('name')
__root__ = __settings__.getAddonInfo('path')

if __name__ == "__main__":
    from Tfp import Tfp
    tfp = Tfp()
    tfp.execute()
    del tfp

gc.collect()
