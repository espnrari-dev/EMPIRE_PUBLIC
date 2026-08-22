import hashlib, json

GENESIS = "0" * 64

def raw_hash_of(raw_obs: dict) -> str:
    """Canonical hash of a raw observation payload."""
    return hashlib.sha256(
        json.dumps(raw_obs, sort_keys=True).encode()
    ).hexdigest()

def chain_hash(prev_hash: str, raw_hash: str, cycle: int) -> str:
    """Canonical link hash. Only place this formula may live."""
    return hashlib.sha256(f"{prev_hash}:{raw_hash}:{cycle}".encode()).hexdigest()
