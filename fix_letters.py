# -*- coding: utf-8 -*-
"""
บรรทัดคำสั่งเดิมของบฑ.31 (ไฟล์ Export) — คงไว้เพื่อให้คำสั่ง/สคริปต์เดิมใช้ได้
โค้ดจริงย้ายไปอยู่ที่ doctypes/bt31/ (export.py, letter.py, layout.py) และ core/

    python fix_letters.py "Export (90).doc" "Export (91).doc" [--pdf] [-o DIR] [--doc] [--no-supervisor]
"""
import sys

from core import ASSETS, BASE                                      # noqa: F401
from core.render import LOGO_FILE, LOGO_URL, logo_source, unique, word_convert   # noqa: F401
from core.text import *                                            # noqa: F401,F403
from core.wordhtml import TEXT_WIDTH, signature_block, text_width_pt, wrap_document   # noqa: F401
from doctypes.bt31.export import *                                 # noqa: F401,F403
from doctypes.bt31.layout import *                                 # noqa: F401,F403
from doctypes.bt31.letter import *                                 # noqa: F401,F403
from doctypes.bt31.export import main

if __name__ == "__main__":
    sys.exit(main())
