"""食事記録コンテキストのエラー。メッセージはそのまま利用者（チャット）に見せる。"""


class MealError(Exception):
    """ドメインの決まりに反する操作。"""


class NotFound(MealError):
    """指定された食事・いつもの・品目がない。"""
