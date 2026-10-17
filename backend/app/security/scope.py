from dataclasses import dataclass

ROLE_LEVEL = {"EMPLOYEE": 0, "MANAGER": 1, "ADMIN": 2}


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    user_id: str
    role: str

    @property
    def level(self):
        return ROLE_LEVEL[self.role]
