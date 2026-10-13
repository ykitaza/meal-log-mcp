from domain.values import EaterId


class SubjectAsEaterId:
    """EaterResolver の実装（勉強用）。sub をそのまま食べた人の ID として使う。"""

    async def resolve(self, subject: str) -> EaterId:
        return EaterId(subject)
