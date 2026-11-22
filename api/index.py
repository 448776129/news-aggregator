"""Vercel Serverless 入口：把 FastAPI 应用包成 AWS Lambda handler。"""
from __future__ import annotations

import os
import sys

# Vercel 会把 api/ 作为部署根目录之一，手动把项目根加入 import path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.api import app  # noqa: E402
from mangum import Mangum  # noqa: E402

handler = Mangum(app, lifespan="off")
