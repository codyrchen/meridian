from enum import StrEnum


class ReleaseType(StrEnum):
    CLIFF = "cliff"
    LINEAR = "linear"
    EMISSION = "emission"
    MILESTONE = "milestone"
    GOVERNANCE = "governance"
    UNKNOWN = "unknown"


class AllocationBucket(StrEnum):
    TEAM = "team"
    INVESTOR = "investor"
    FOUNDATION = "foundation"
    COMMUNITY = "community"
    ECOSYSTEM = "ecosystem"
    TREASURY = "treasury"
    AIRDROP = "airdrop"
    REWARDS = "rewards"
    UNKNOWN = "unknown"


class SourceConfidence(StrEnum):
    VERIFIED_PRIMARY = "verified_primary"
    VERIFIED_SECONDARY = "verified_secondary"
    UNVERIFIED = "unverified"


class LicenseClass(StrEnum):
    PUBLIC = "public"
    ATTRIBUTION_REQUIRED = "attribution_required"
    RESTRICTED = "restricted"


class EventKind(StrEnum):
    """Distinguishes scheduled unlocks from observed on-chain flows."""

    SCHEDULED = "scheduled"
    OBSERVED_TRANSFER = "observed_transfer"
    OBSERVED_EXCHANGE_DEPOSIT = "observed_exchange_deposit"


class AmountProvenance(StrEnum):
    REPORTED = "reported"  # stated verbatim by a primary source
    DERIVED = "derived"  # computed; a recorded derivation is mandatory


class SourceRole(StrEnum):
    PRIMARY = "primary"
    SECONDARY_CROSS_CHECK = "secondary_cross_check"
    ONCHAIN_VERIFICATION = "onchain_verification"


class ClaimType(StrEnum):
    """What claim a linked source supports for an event version."""

    SCHEDULE = "schedule"
    AMOUNT = "amount"
    ALLOCATION = "allocation"
    COMPOSITION = "composition"
    SUPPLY = "supply"
    OTHER = "other"


class VestingCadence(StrEnum):
    CLIFF = "cliff"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    CONTINUOUS = "continuous"
    IRREGULAR = "irregular"
    UNKNOWN = "unknown"


class SupplyMethod(StrEnum):
    REPORTED = "reported"  # stated by an archived source for that date
    IMPLIED_MARKET_CAP = "implied_market_cap"  # market_cap_usd / close from our own bars
