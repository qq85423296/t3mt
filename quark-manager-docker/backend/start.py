# -*- coding: utf-8 -*-
"""
应用启动脚本
"""
import os
import sys

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import main

if __name__ == '__main__':
    main()
