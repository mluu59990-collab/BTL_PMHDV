"""Lỗi nghiệp vụ. Tầng presentation sẽ map sang HTTP status."""


class DomainError(Exception):
    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """404"""


class ConflictError(DomainError):
    """409 - trùng dữ liệu / vi phạm ràng buộc"""


class AuthenticationError(DomainError):
    """401 - chưa đăng nhập / token sai / hết hạn"""


class PermissionDeniedError(DomainError):
    """403 - đã đăng nhập nhưng không đủ quyền"""


class BusinessRuleError(DomainError):
    """422 - vi phạm quy tắc nghiệp vụ"""
