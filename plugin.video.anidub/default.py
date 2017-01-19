# -*- coding: utf-8 -*-

import gc
import xbmcaddon

__settings__ = xbmcaddon.Addon(id='plugin.video.anidub')
__plugin__ = __settings__.getAddonInfo('name')
__root__ = __settings__.getAddonInfo('path')


if __name__ == "__main__":
    from AniDub import Main
    ad = Main()
    ad.execute()
    del ad

gc.collect()
