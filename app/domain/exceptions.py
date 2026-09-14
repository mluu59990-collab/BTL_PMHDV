class DomainError(Exception):
    """Lỗi nghiệp vụ có thông điệp an toàn để trả cho người dùng."""


class ResourceNotFound(DomainError):
    pass


class ConflictError(DomainError):
    pass
