"""Lỗi xác thực dùng bởi JWT provider và API."""


class AuthenticationError(Exception):
    """Token thiếu, không hợp lệ, hết hạn hoặc sai loại."""
