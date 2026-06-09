from abc import ABC, abstractmethod
from typing import Any


class DataMigration(ABC):
    revision: str
    depends_on: list[str] = []
    description: str = ""

    @abstractmethod
    def upgrade(self, conn: Any) -> None: ...

    def validate(self, conn: Any) -> None:
        pass
