# -*- coding: utf-8 -*-
"""
บรรทัดคำสั่งเดิมของบฑ.31 (PDF e-Form) — คงไว้เพื่อให้คำสั่ง/สคริปต์เดิมใช้ได้
โค้ดจริงย้ายไปอยู่ที่ doctypes/bt31/eform.py

    python bt31.py "<บฑ31>.pdf" [--approve] [--pdf] [-o DIR] [--show] [--en "program=..."]
"""
import sys

from doctypes.bt31.eform import *        # noqa: F401,F403
from doctypes.bt31.eform import main

if __name__ == "__main__":
    sys.exit(main())
