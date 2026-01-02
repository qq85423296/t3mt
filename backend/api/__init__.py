# -*- coding: utf-8 -*-
"""
API模块初始化
"""
from .auth import auth_bp
from .accounts import accounts_bp
from .quark import quark_bp
from .search import search_bp
from .transfer import transfer_bp
from .download import download_bp
from .config import config_bp

__all__ = [
    'auth_bp',
    'accounts_bp',
    'quark_bp',
    'search_bp',
    'transfer_bp',
    'download_bp',
    'config_bp'
]
