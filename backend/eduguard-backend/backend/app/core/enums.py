import enum


class SubscriptionType(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

    def __str__(self):
        return self.value