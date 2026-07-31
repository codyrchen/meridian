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
