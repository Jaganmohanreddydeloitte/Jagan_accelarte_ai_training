"""
Intelligent caching system for the Agentic Medallion Pipeline.

This module implements a multi-level cache to:
1. Skip repeated profiling of identical files (file content hash)
2. Reuse previous STTM generation results (content-based)
3. Cache LLM API responses to minimize API calls
4. Track cache hit/miss rates and statistics

Cache Key Generation:
- File cache: hash(file_content) → profile
- STTM cache: hash(file_content + layer + business_intent) → sttm
- LLM cache: hash(prompt + model) → response

Cache Invalidation:
- File changes are detected via content hash
- Cache age can be set per cache type
- Manual invalidation via clear_cache()
"""

import json
import hashlib
import threading
from pathlib import Path
from typing import Optional, Any, Dict, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import time

from core.config import BASE_DIR


# ─── Cache Directory ────────────────────────────────────────────────────────

CACHE_DIR = BASE_DIR / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

# Subdirectories for different cache types
PROFILE_CACHE_DIR = CACHE_DIR / "profiles"
STTM_CACHE_DIR = CACHE_DIR / "sttm"
LLM_CACHE_DIR = CACHE_DIR / "llm"

PROFILE_CACHE_DIR.mkdir(exist_ok=True)
STTM_CACHE_DIR.mkdir(exist_ok=True)
LLM_CACHE_DIR.mkdir(exist_ok=True)


# ─── Cache Configuration ────────────────────────────────────────────────────

@dataclass
class CacheConfig:
    """Configuration for cache behavior."""
    profile_cache_ttl: int = 86400 * 30  # 30 days in seconds
    sttm_cache_ttl: int = 86400 * 7     # 7 days
    llm_cache_ttl: int = 86400 * 365    # 1 year (LLM responses don't change)
    enabled: bool = True                 # Global cache enable/disable
    max_cache_size_mb: int = 1000        # Max cache directory size


# ─── Cache Entry Metadata ───────────────────────────────────────────────────

@dataclass
class CacheEntry:
    """Metadata for a cached item."""
    key: str
    cache_type: str  # "profile", "sttm", "llm"
    created_at: str  # ISO timestamp
    expires_at: str  # ISO timestamp (or empty if never expires)
    size_bytes: int
    hit_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if not self.expires_at:
            return False
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.utcnow() > expires
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# ─── Hash Functions ────────────────────────────────────────────────────────

def hash_file(file_path: str) -> str:
    """
    Generate SHA256 hash of file contents.
    
    Used for cache keys - identical files produce identical hashes.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def hash_string(text: str) -> str:
    """Generate SHA256 hash of string."""
    return hashlib.sha256(text.encode()).hexdigest()


def hash_dict(data: Dict[str, Any]) -> str:
    """Generate hash of dictionary (sorted for consistency)."""
    json_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()


# ─── Cache Manager ──────────────────────────────────────────────────────────

class CacheManager:
    """Thread-safe cache manager for profiles, STTM, and LLM responses."""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialize cache manager.
        
        Args:
            config: CacheConfig object (uses defaults if None)
        """
        self.config = config or CacheConfig()
        self._lock = threading.Lock()
        self._metadata = {}  # In-memory metadata index
        self._load_metadata()
        self._stats = {
            "profile_hits": 0,
            "profile_misses": 0,
            "sttm_hits": 0,
            "sttm_misses": 0,
            "llm_hits": 0,
            "llm_misses": 0,
        }
    
    def _load_metadata(self) -> None:
        """Load cache metadata index from disk."""
        metadata_file = CACHE_DIR / "metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file) as f:
                    data = json.load(f)
                    self._metadata = {k: CacheEntry(**v) for k, v in data.items()}
            except Exception as e:
                print(f"Warning: Failed to load cache metadata: {e}")
                self._metadata = {}
    
    def _save_metadata(self) -> None:
        """Save cache metadata index to disk."""
        metadata_file = CACHE_DIR / "metadata.json"
        try:
            with open(metadata_file, "w") as f:
                data = {k: v.to_dict() for k, v in self._metadata.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save cache metadata: {e}")
    
    def _get_profile_key(self, file_path: str) -> str:
        """Generate cache key for file profile."""
        file_hash = hash_file(file_path)
        return f"profile_{file_hash}"
    
    def _get_sttm_key(
        self,
        file_path: str,
        layer: str,
        business_intent: str
    ) -> str:
        """Generate cache key for STTM."""
        file_hash = hash_file(file_path)
        context = f"{file_hash}_{layer}_{business_intent}"
        context_hash = hash_string(context)
        return f"sttm_{layer}_{context_hash}"
    
    def _get_llm_key(self, prompt: str, model: str) -> str:
        """Generate cache key for LLM response."""
        key_data = f"{prompt}_{model}"
        key_hash = hash_string(key_data)
        return f"llm_{model[:10]}_{key_hash}"
    
    def _create_cache_entry(
        self,
        key: str,
        cache_type: str,
        data: Any,
        ttl: Optional[int] = None
    ) -> CacheEntry:
        """Create cache entry with metadata."""
        now = datetime.utcnow().isoformat() + "Z"
        
        # Determine TTL
        if ttl is None:
            if cache_type == "profile":
                ttl = self.config.profile_cache_ttl
            elif cache_type == "sttm":
                ttl = self.config.sttm_cache_ttl
            elif cache_type == "llm":
                ttl = self.config.llm_cache_ttl
            else:
                ttl = 86400  # 1 day default
        
        expires_at = ""
        if ttl > 0:
            expires = datetime.utcnow() + timedelta(seconds=ttl)
            expires_at = expires.isoformat() + "Z"
        
        # Calculate size
        if isinstance(data, (dict, list)):
            size = len(json.dumps(data).encode())
        else:
            size = len(str(data).encode())
        
        return CacheEntry(
            key=key,
            cache_type=cache_type,
            created_at=now,
            expires_at=expires_at,
            size_bytes=size,
            hit_count=0
        )
    
    def cache_profile(
        self,
        file_path: str,
        profile_data: Dict[str, Any]
    ) -> None:
        """
        Cache a file profile.
        
        Args:
            file_path: Path to the file
            profile_data: Profile dictionary to cache
        """
        if not self.config.enabled:
            return
        
        with self._lock:
            key = self._get_profile_key(file_path)
            cache_file = PROFILE_CACHE_DIR / f"{key}.json"
            
            # Save data
            with open(cache_file, "w") as f:
                json.dump(profile_data, f, indent=2)
            
            # Update metadata
            entry = self._create_cache_entry(key, "profile", profile_data)
            self._metadata[key] = entry
            self._save_metadata()
    
    def get_cached_profile(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached profile if available and not expired.
        
        Args:
            file_path: Path to the file
        
        Returns:
            Profile dictionary or None if not cached/expired
        """
        if not self.config.enabled:
            self._stats["profile_misses"] += 1
            return None
        
        with self._lock:
            key = self._get_profile_key(file_path)
            
            # Check metadata
            if key not in self._metadata:
                self._stats["profile_misses"] += 1
                return None
            
            entry = self._metadata[key]
            
            # Check if expired
            if entry.is_expired():
                self._stats["profile_misses"] += 1
                self._invalidate_cache_entry(key)
                return None
            
            # Load and return
            cache_file = PROFILE_CACHE_DIR / f"{key}.json"
            if not cache_file.exists():
                self._stats["profile_misses"] += 1
                self._invalidate_cache_entry(key)
                return None
            
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                
                # Update hit count
                entry.hit_count += 1
                self._metadata[key] = entry
                self._stats["profile_hits"] += 1
                self._save_metadata()
                
                return data
            except Exception as e:
                print(f"Error loading cached profile: {e}")
                self._stats["profile_misses"] += 1
                return None
    
    def cache_sttm(
        self,
        file_path: str,
        layer: str,
        business_intent: str,
        sttm_data: Dict[str, Any]
    ) -> None:
        """
        Cache STTM (transformation rules).
        
        Args:
            file_path: Path to the file
            layer: Layer name (bronze, silver, gold)
            business_intent: User's business intent
            sttm_data: STTM dictionary to cache
        """
        if not self.config.enabled:
            return
        
        with self._lock:
            key = self._get_sttm_key(file_path, layer, business_intent)
            cache_file = STTM_CACHE_DIR / f"{key}.json"
            
            # Save data
            with open(cache_file, "w") as f:
                json.dump(sttm_data, f, indent=2)
            
            # Update metadata
            entry = self._create_cache_entry(key, "sttm", sttm_data)
            self._metadata[key] = entry
            self._save_metadata()
    
    def get_cached_sttm(
        self,
        file_path: str,
        layer: str,
        business_intent: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached STTM if available and not expired.
        
        Args:
            file_path: Path to the file
            layer: Layer name
            business_intent: Business intent
        
        Returns:
            STTM dictionary or None if not cached/expired
        """
        if not self.config.enabled:
            self._stats["sttm_misses"] += 1
            return None
        
        with self._lock:
            key = self._get_sttm_key(file_path, layer, business_intent)
            
            if key not in self._metadata:
                self._stats["sttm_misses"] += 1
                return None
            
            entry = self._metadata[key]
            
            if entry.is_expired():
                self._stats["sttm_misses"] += 1
                self._invalidate_cache_entry(key)
                return None
            
            cache_file = STTM_CACHE_DIR / f"{key}.json"
            if not cache_file.exists():
                self._stats["sttm_misses"] += 1
                self._invalidate_cache_entry(key)
                return None
            
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                
                entry.hit_count += 1
                self._metadata[key] = entry
                self._stats["sttm_hits"] += 1
                self._save_metadata()
                
                return data
            except Exception as e:
                print(f"Error loading cached STTM: {e}")
                self._stats["sttm_misses"] += 1
                return None
    
    def cache_llm_response(
        self,
        prompt: str,
        model: str,
        response: str
    ) -> None:
        """
        Cache LLM API response.
        
        Args:
            prompt: The prompt sent to LLM
            model: Model name (e.g., "gpt-4o-mini")
            response: LLM response text
        """
        if not self.config.enabled:
            return
        
        with self._lock:
            key = self._get_llm_key(prompt, model)
            cache_file = LLM_CACHE_DIR / f"{key}.json"
            
            data = {
                "prompt": prompt,
                "model": model,
                "response": response,
                "cached_at": datetime.utcnow().isoformat() + "Z"
            }
            
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)
            
            entry = self._create_cache_entry(key, "llm", data)
            self._metadata[key] = entry
            self._save_metadata()
    
    def get_cached_llm_response(self, prompt: str, model: str) -> Optional[str]:
        """
        Retrieve cached LLM response.
        
        Args:
            prompt: The prompt
            model: Model name
        
        Returns:
            LLM response or None if not cached
        """
        if not self.config.enabled:
            self._stats["llm_misses"] += 1
            return None
        
        with self._lock:
            key = self._get_llm_key(prompt, model)
            
            if key not in self._metadata:
                self._stats["llm_misses"] += 1
                return None
            
            entry = self._metadata[key]
            
            if entry.is_expired():
                self._stats["llm_misses"] += 1
                self._invalidate_cache_entry(key)
                return None
            
            cache_file = LLM_CACHE_DIR / f"{key}.json"
            if not cache_file.exists():
                self._stats["llm_misses"] += 1
                self._invalidate_cache_entry(key)
                return None
            
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                
                entry.hit_count += 1
                self._metadata[key] = entry
                self._stats["llm_hits"] += 1
                self._save_metadata()
                
                return data["response"]
            except Exception as e:
                print(f"Error loading cached LLM response: {e}")
                self._stats["llm_misses"] += 1
                return None
    
    def _invalidate_cache_entry(self, key: str) -> None:
        """Remove a single cache entry."""
        if key not in self._metadata:
            return
        
        entry = self._metadata[key]
        cache_type = entry.cache_type
        
        # Remove file
        if cache_type == "profile":
            cache_file = PROFILE_CACHE_DIR / f"{key}.json"
        elif cache_type == "sttm":
            cache_file = STTM_CACHE_DIR / f"{key}.json"
        else:  # llm
            cache_file = LLM_CACHE_DIR / f"{key}.json"
        
        if cache_file.exists():
            cache_file.unlink()
        
        # Remove metadata
        del self._metadata[key]
    
    def clear_cache(
        self,
        cache_type: Optional[str] = None,
        older_than_days: Optional[int] = None
    ) -> int:
        """
        Clear cache entries.
        
        Args:
            cache_type: Type to clear ("profile", "sttm", "llm", or None for all)
            older_than_days: Only clear entries older than N days
        
        Returns:
            Number of entries cleared
        """
        with self._lock:
            keys_to_clear = []
            cutoff_date = None
            
            if older_than_days:
                cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
            
            for key, entry in self._metadata.items():
                # Filter by cache type
                if cache_type and entry.cache_type != cache_type:
                    continue
                
                # Filter by age
                if cutoff_date:
                    created = datetime.fromisoformat(entry.created_at.rstrip("Z"))
                    if created > cutoff_date:
                        continue
                
                keys_to_clear.append(key)
            
            # Clear entries
            for key in keys_to_clear:
                self._invalidate_cache_entry(key)
            
            self._save_metadata()
            return len(keys_to_clear)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        profile_total = self._stats["profile_hits"] + self._stats["profile_misses"]
        sttm_total = self._stats["sttm_hits"] + self._stats["sttm_misses"]
        llm_total = self._stats["llm_hits"] + self._stats["llm_misses"]
        
        return {
            "enabled": self.config.enabled,
            "total_entries": len(self._metadata),
            "profile": {
                "hits": self._stats["profile_hits"],
                "misses": self._stats["profile_misses"],
                "total": profile_total,
                "hit_rate": (
                    self._stats["profile_hits"] / profile_total * 100
                    if profile_total > 0 else 0
                ),
            },
            "sttm": {
                "hits": self._stats["sttm_hits"],
                "misses": self._stats["sttm_misses"],
                "total": sttm_total,
                "hit_rate": (
                    self._stats["sttm_hits"] / sttm_total * 100
                    if sttm_total > 0 else 0
                ),
            },
            "llm": {
                "hits": self._stats["llm_hits"],
                "misses": self._stats["llm_misses"],
                "total": llm_total,
                "hit_rate": (
                    self._stats["llm_hits"] / llm_total * 100
                    if llm_total > 0 else 0
                ),
            },
            "cache_dir_size_mb": self._get_cache_dir_size_mb(),
        }
    
    def _get_cache_dir_size_mb(self) -> float:
        """Get total cache directory size in MB."""
        total_bytes = 0
        for cache_dir in [PROFILE_CACHE_DIR, STTM_CACHE_DIR, LLM_CACHE_DIR]:
            for file in cache_dir.glob("*.json"):
                total_bytes += file.stat().st_size
        return total_bytes / (1024 * 1024)


# ─── Singleton Instance ─────────────────────────────────────────────────────

_cache_manager = None


def get_cache_manager() -> CacheManager:
    """Get or create the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


# ─── Decorator for Easy Caching ─────────────────────────────────────────────

def with_profile_cache(func: Callable) -> Callable:
    """
    Decorator to automatically cache profile results.
    
    Function must accept file_path as first argument.
    
    Example:
        @with_profile_cache
        def profile_dataset(file_path, ...):
            ...
    """
    def wrapper(file_path: str, *args, **kwargs):
        cache_mgr = get_cache_manager()
        
        # Try to get from cache
        cached = cache_mgr.get_cached_profile(file_path)
        if cached is not None:
            print(f"✓ Using cached profile for {Path(file_path).name}")
            return cached
        
        # Not in cache, execute function
        result = func(file_path, *args, **kwargs)
        
        # Cache result
        if result:
            cache_mgr.cache_profile(file_path, result)
        
        return result
    
    return wrapper


def with_sttm_cache(layer: str) -> Callable:
    """
    Decorator to automatically cache STTM results.
    
    Function must accept (file_path, business_intent, ...) as arguments.
    
    Example:
        @with_sttm_cache("bronze")
        def generate_bronze_sttm(file_path, business_intent, ...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(file_path: str, business_intent: str, *args, **kwargs):
            cache_mgr = get_cache_manager()
            
            # Try to get from cache
            cached = cache_mgr.get_cached_sttm(file_path, layer, business_intent)
            if cached is not None:
                print(f"✓ Using cached STTM for {layer} layer")
                return cached
            
            # Not in cache, execute function
            result = func(file_path, business_intent, *args, **kwargs)
            
            # Cache result
            if result:
                cache_mgr.cache_sttm(file_path, layer, business_intent, result)
            
            return result
        
        return wrapper
    
    return decorator
