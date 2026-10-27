"""Các kiểu dữ liệu đầu vào dùng chung giữa các API."""

from typing import Annotated

from pydantic import Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9]{8,15}$")]
PositiveID = Annotated[int, Field(gt=0, le=9223372036854775807)]


Note = Annotated[str, StringConstraints(max_length=2000)]
