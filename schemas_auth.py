from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class RegisterCompanyRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=100)
    industry: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)

    @field_validator("company_name")
    @classmethod
    def clean_company_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Company name is required")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 bytes")
        return value


class CompanyOut(BaseModel):
    id: int
    company_name: str = Field(
        validation_alias=AliasChoices("name", "company_name"),
        serialization_alias="company_name",
    )
    industry: str | None = None
    location: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):
    id: int
    company_id: int
    email: EmailStr
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class RegisterResponse(BaseModel):
    company: CompanyOut
    user: UserOut


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"