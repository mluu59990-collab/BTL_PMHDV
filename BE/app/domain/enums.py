from enum import Enum


class RoleCode(str, Enum):
    ADMIN = "ADMIN"
    SALE = "SALE"
    PURCHASER = "PURCHASER"
    WAREHOUSE = "WAREHOUSE"
    ACCOUNTANT = "ACCOUNTANT"
    CUSTOMER = "CUSTOMER"


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    LOCKED = "LOCKED"


class CurrencyCode(str, Enum):
    CNY = "CNY"  # NDT
    USD = "USD"


class FeeUnit(str, Enum):
    PERCENT = "PERCENT"
    VND = "VND"
    VND_PER_KG = "VND_PER_KG"
    VND_PER_M3 = "VND_PER_M3"
    VND_PER_ITEM = "VND_PER_ITEM"
    VND_PER_PACKAGE = "VND_PER_PACKAGE"


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"
