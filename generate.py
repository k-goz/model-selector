#!/usr/bin/env python3
"""
从 OpenRouter API 拉取最新模型数据，重新生成 index.html
用法: python3 generate.py
依赖: curl, python3（自动处理，无需手动安装）
"""
import json, os, subprocess, tempfile
from datetime import datetime

URL = "https://openrouter.ai/api/v1/models"
CACHE = "/tmp/openrouter_models.json"
HTML  = "index.html"

def main():
    print("从 OpenRouter 获取最新模型数据...")
    subprocess.run(
        ["curl", "-s", URL, "-A", "Mozilla/5.0", "-o", CACHE],
        check=True
    )
    print("生成 index.html...")
    subprocess.run(["python3", os.path.abspath(__file__).replace("generate.py", "build.py")],
                   check=True)
    print(f"完成！更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    main()
