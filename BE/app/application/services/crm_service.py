from dataclasses import replace

from app.domain.crm import (
    CareTask,
    Customer,
    SalesPlan,
    ServiceReview,
    VipMembership,
    VipPackage,
)
from app.domain.enums import RoleCode
from app.domain.exceptions import (
    BusinessRuleError,
    NotFoundError,
    PermissionDeniedError,
)


class CrmService:
    """CRM authorization and validation stay inside the transaction boundary."""

    def __init__(self, repository, entity, customers, packages, users, uow, actor):
        self.repository, self.entity = repository, entity
        self.customers, self.packages, self.users = customers, packages, users
        self.uow, self.actor = uow, actor

    def admin(self):
        if self.actor.role != RoleCode.ADMIN:
            raise PermissionDeniedError("Chỉ Admin được thực hiện thao tác này")

    async def get(self, record_id, *, for_update=False):
        record = await self.repository.get(record_id, for_update=for_update)
        if record is None:
            raise NotFoundError("Không tìm thấy bản ghi CRM")
        await self.access(record)
        return record

    async def access(self, record):
        if self.actor.role == RoleCode.ADMIN:
            return
        if self.actor.role != RoleCode.SALE:
            raise PermissionDeniedError("Bạn không có quyền truy cập CRM")
        if isinstance(record, VipPackage):
            return
        owner = record
        if hasattr(record, "customer_id"):
            owner = await self.customers.get(record.customer_id, for_update=True)
        if owner is None or owner.sale_id != self.actor.id:
            raise PermissionDeniedError(
                "Khách hàng/kế hoạch không thuộc Sale phụ trách"
            )

    async def validate(self, record, changes=None):
        if isinstance(record, (VipPackage, VipMembership)):
            self.admin()
        if isinstance(record, Customer):
            if self.actor.role != RoleCode.ADMIN:
                if changes is None:
                    record.sale_id = self.actor.id
                elif {"sale_id", "user_id", "credit_limit"} & changes.keys():
                    self.admin()
                if changes is None and (
                    record.user_id is not None or record.credit_limit != 0
                ):
                    self.admin()
            if record.user_id is not None:
                user = await self.users.get_by_id(record.user_id)
                if user is None or not user.is_active or user.role != RoleCode.CUSTOMER:
                    raise BusinessRuleError(
                        "Tài khoản liên kết phải là CUSTOMER đang hoạt động"
                    )
        if hasattr(record, "sale_id") and record.sale_id is not None:
            sale = await self.users.get_by_id(record.sale_id)
            if sale is None or not sale.is_active or sale.role != RoleCode.SALE:
                raise BusinessRuleError(
                    "Nhân viên phụ trách phải là SALE đang hoạt động"
                )
        if hasattr(record, "customer_id"):
            customer = await self.customers.get(record.customer_id, for_update=True)
            if customer is None or not customer.is_active:
                raise BusinessRuleError(
                    "Khách hàng không tồn tại hoặc đã ngừng hoạt động"
                )
        await self.access(record)
        if isinstance(record, SalesPlan) and (
            record.period_start.day != 1
            or (
                record.period_type == "QUARTER"
                and record.period_start.month not in (1, 4, 7, 10)
            )
        ):
            raise BusinessRuleError("Kỳ phải bắt đầu vào ngày đầu tháng/quý")
        if (
            isinstance(record, ServiceReview)
            and record.period_end < record.period_start
        ):
            raise BusinessRuleError("Ngày kết thúc phải từ ngày bắt đầu trở đi")
        if isinstance(record, VipMembership):
            package = await self.packages.get(record.package_id, for_update=True)
            if package is None or not package.is_active:
                raise BusinessRuleError("Gói VIP không tồn tại hoặc đã ngừng hoạt động")
            if (
                record.valid_until < record.valid_from
                or (record.valid_until - record.valid_from).days
                >= package.duration_days
            ):
                raise BusinessRuleError(
                    "Thời hạn đăng ký vượt thời hạn gói VIP hoặc không hợp lệ"
                )
            if record.is_active and await self.repository.membership_overlaps(
                record.customer_id, record.valid_from, record.valid_until, record.id
            ):
                raise BusinessRuleError(
                    "Khách hàng đã có gói VIP trong khoảng thời gian này"
                )

    async def create(self, data):
        record = self.entity(**data)
        if isinstance(record, CareTask) and record.status != "NEW":
            raise BusinessRuleError("Quy trình CSKH phải bắt đầu ở bước NEW")
        await self.validate(record)
        result = await self.repository.add(record)
        await self.uow.commit()
        return result

    async def update(self, record_id, changes):
        record = await self.get(record_id, for_update=True)
        if isinstance(record, CareTask) and "status" in changes:
            allowed = {
                "NEW": {"CONTACTED", "CANCELLED"},
                "CONTACTED": {"FOLLOW_UP", "COMPLETED", "CANCELLED"},
                "FOLLOW_UP": {"COMPLETED", "CANCELLED"},
                "COMPLETED": set(),
                "CANCELLED": set(),
            }
            if (
                changes["status"] != record.status
                and changes["status"] not in allowed[record.status]
            ):
                raise BusinessRuleError("Bước CSKH không hợp lệ")
        updated = replace(record, **changes)
        await self.validate(updated, changes)
        result = await self.repository.update(record_id, changes)
        await self.uow.commit()
        return result

    async def deactivate(self, record_id):
        record = await self.get(record_id, for_update=True)
        if isinstance(record, (VipPackage, VipMembership)):
            self.admin()
        await self.repository.update(record_id, {"is_active": False})
        await self.uow.commit()

    async def list(self, *, filters=None, **kwargs):
        filters = dict(filters or {})
        if self.actor.role == RoleCode.SALE:
            if self.entity in (Customer, SalesPlan):
                if filters.get("sale_id") not in (None, self.actor.id):
                    raise PermissionDeniedError("Không được xem dữ liệu Sale khác")
                filters["sale_id"] = self.actor.id
            elif self.entity != VipPackage:
                if filters.get("owner_sale_id") not in (None, self.actor.id):
                    raise PermissionDeniedError("Không được xem dữ liệu Sale khác")
                filters["owner_sale_id"] = self.actor.id
        if (
            filters.get("date_from")
            and filters.get("date_to")
            and filters["date_from"] > filters["date_to"]
        ):
            raise BusinessRuleError("Khoảng thời gian không hợp lệ")
        return await self.repository.list(filters=filters, **kwargs)
