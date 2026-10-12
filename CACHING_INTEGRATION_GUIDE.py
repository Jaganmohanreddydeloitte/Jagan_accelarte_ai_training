"""
Caching Integration Guide - Shows how to integrate cache checks into pipeline agents.

This guide demonstrates the exact locations to add caching in your existing code.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION GUIDE: Where to Add Cache Checks
# ═══════════════════════════════════════════════════════════════════════════════

# ─── EXAMPLE 1: Profile Agent ────────────────────────────────────────────────
# File: agents/profiler.py

"""
BEFORE (No caching):

def profile_dataset(file_path: str, run_id: str) -> Path:
    '''Profile a CSV/XLSX file.'''
    # Read file
    df = pd.read_csv(file_path)
    
    # Analyze
    profile = {
        "columns": list(df.columns),
        "dtypes": df.dtypes.to_dict(),
        "null_counts": df.isnull().sum().to_dict(),
        ...
    }
    
    # Save
    profile_path = PROFILES_DIR / f"profile_{run_id}.json"
    with open(profile_path, "w") as f:
        json.dump(profile, f, indent=2)
    
    return profile_path
"""

# AFTER (With caching):

from core.caching import get_cache_manager

def profile_dataset(file_path: str, run_id: str) -> Path:
    """Profile a CSV/XLSX file with caching."""
    
    cache_mgr = get_cache_manager()
    
    # 1. TRY CACHE FIRST
    cached_profile = cache_mgr.get_cached_profile(file_path)
    if cached_profile is not None:
        print(f"✓ Cache HIT: Using cached profile for {Path(file_path).name}")
        # Still save locally for this run
        profile_path = PROFILES_DIR / f"profile_{run_id}.json"
        with open(profile_path, "w") as f:
            json.dump(cached_profile, f, indent=2)
        return profile_path
    
    # 2. IF CACHE MISS, DO THE WORK
    print(f"✗ Cache MISS: Generating new profile for {Path(file_path).name}")
    
    df = pd.read_csv(file_path)
    
    profile = {
        "columns": list(df.columns),
        "dtypes": df.dtypes.to_dict(),
        "null_counts": df.isnull().sum().to_dict(),
        ...
    }
    
    # 3. SAVE TO CACHE
    cache_mgr.cache_profile(file_path, profile)
    
    # 4. SAVE LOCALLY FOR THIS RUN
    profile_path = PROFILES_DIR / f"profile_{run_id}.json"
    with open(profile_path, "w") as f:
        json.dump(profile, f, indent=2)
    
    return profile_path


# ─── EXAMPLE 2: STTM Generator Agent ────────────────────────────────────────
# File: agents/sttm_generator.py

"""
BEFORE (No caching):

def generate_bronze_sttm(
    file_path: str,
    profile_path: str,
    business_intent: str,
    run_id: str
) -> Path:
    '''Generate Bronze layer STTM using LLM.'''
    
    # Call LLM
    sttm = llm_agent.generate_sttm(
        file_path=file_path,
        profile_path=profile_path,
        layer="bronze",
        business_intent=business_intent
    )
    
    # Save
    sttm_path = STTM_DIR / f"sttm_bronze_{run_id}.json"
    with open(sttm_path, "w") as f:
        json.dump(sttm, f, indent=2)
    
    return sttm_path
"""

# AFTER (With caching):

from core.caching import get_cache_manager

def generate_bronze_sttm(
    file_path: str,
    profile_path: str,
    business_intent: str,
    run_id: str
) -> Path:
    """Generate Bronze layer STTM with caching."""
    
    cache_mgr = get_cache_manager()
    layer = "bronze"
    
    # 1. TRY CACHE FIRST
    cached_sttm = cache_mgr.get_cached_sttm(file_path, layer, business_intent)
    if cached_sttm is not None:
        print(f"✓ Cache HIT: Using cached {layer} STTM")
        # Still save locally for this run
        sttm_path = STTM_DIR / f"sttm_{layer}_{run_id}.json"
        with open(sttm_path, "w") as f:
            json.dump(cached_sttm, f, indent=2)
        return sttm_path
    
    # 2. IF CACHE MISS, CALL LLM
    print(f"✗ Cache MISS: Generating new {layer} STTM via LLM")
    
    sttm = llm_agent.generate_sttm(
        file_path=file_path,
        profile_path=profile_path,
        layer=layer,
        business_intent=business_intent
    )
    
    # 3. SAVE TO CACHE
    cache_mgr.cache_sttm(file_path, layer, business_intent, sttm)
    
    # 4. SAVE LOCALLY FOR THIS RUN
    sttm_path = STTM_DIR / f"sttm_{layer}_{run_id}.json"
    with open(sttm_path, "w") as f:
        json.dump(sttm, f, indent=2)
    
    return sttm_path


# Repeat for silver and gold:

def generate_silver_sttm(file_path: str, profile_path: str, business_intent: str, run_id: str) -> Path:
    cache_mgr = get_cache_manager()
    layer = "silver"
    
    cached_sttm = cache_mgr.get_cached_sttm(file_path, layer, business_intent)
    if cached_sttm is not None:
        print(f"✓ Cache HIT: Using cached {layer} STTM")
        sttm_path = STTM_DIR / f"sttm_{layer}_{run_id}.json"
        with open(sttm_path, "w") as f:
            json.dump(cached_sttm, f, indent=2)
        return sttm_path
    
    print(f"✗ Cache MISS: Generating new {layer} STTM")
    sttm = llm_agent.generate_sttm(file_path, profile_path, layer, business_intent)
    cache_mgr.cache_sttm(file_path, layer, business_intent, sttm)
    
    sttm_path = STTM_DIR / f"sttm_{layer}_{run_id}.json"
    with open(sttm_path, "w") as f:
        json.dump(sttm, f, indent=2)
    
    return sttm_path


def generate_gold_sttm(file_path: str, profile_path: str, business_intent: str, run_id: str) -> Path:
    cache_mgr = get_cache_manager()
    layer = "gold"
    
    cached_sttm = cache_mgr.get_cached_sttm(file_path, layer, business_intent)
    if cached_sttm is not None:
        print(f"✓ Cache HIT: Using cached {layer} STTM")
        sttm_path = STTM_DIR / f"sttm_{layer}_{run_id}.json"
        with open(sttm_path, "w") as f:
            json.dump(cached_sttm, f, indent=2)
        return sttm_path
    
    print(f"✗ Cache MISS: Generating new {layer} STTM")
    sttm = llm_agent.generate_sttm(file_path, profile_path, layer, business_intent)
    cache_mgr.cache_sttm(file_path, layer, business_intent, sttm)
    
    sttm_path = STTM_DIR / f"sttm_{layer}_{run_id}.json"
    with open(sttm_path, "w") as f:
        json.dump(sttm, f, indent=2)
    
    return sttm_path


# ─── EXAMPLE 3: LLM Wrapper ─────────────────────────────────────────────────
# File: agents/llm_wrapper.py or similar

"""
BEFORE:

def call_llm(prompt: str, model: str) -> str:
    '''Call LLM and return response.'''
    
    # Call API
    if model == "gpt-4o-mini":
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    ...
"""

# AFTER (With LLM response caching):

from core.caching import get_cache_manager

def call_llm(prompt: str, model: str) -> str:
    """Call LLM with response caching."""
    
    cache_mgr = get_cache_manager()
    
    # 1. TRY CACHE FIRST
    cached_response = cache_mgr.get_cached_llm_response(prompt, model)
    if cached_response is not None:
        print(f"✓ Cache HIT: Using cached LLM response (saved API call)")
        return cached_response
    
    # 2. IF CACHE MISS, CALL API
    print(f"✗ Cache MISS: Calling {model} API")
    
    if model == "gpt-4o-mini":
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.choices[0].message.content
    ...
    
    # 3. SAVE TO CACHE
    cache_mgr.cache_llm_response(prompt, model, response_text)
    
    return response_text


# ─── EXAMPLE 4: Streamlit UI Integration ────────────────────────────────────
# File: app/streamlit_app.py

"""
BEFORE:

def main():
    st.set_page_config(page_title="IDAMP", ...)
    
    # ... UI code ...
    
    if st.button("Run Pipeline"):
        profile = profile_dataset(file_path, run_id)
        ...

if __name__ == "__main__":
    main()
"""

# AFTER (With cache UI):

from core.cache_ui import (
    render_cache_status_sidebar,
    render_cache_details_tab,
    render_cache_impact,
    cache_tracking_context
)

def main():
    st.set_page_config(page_title="IDAMP", ...)
    
    # 1. ADD CACHE STATUS TO SIDEBAR
    render_cache_status_sidebar()
    
    # ... existing UI code ...
    
    # 2. ADD CACHE MANAGEMENT TAB
    tab_run, tab_cache, tab_settings = st.tabs(["Run", "Cache", "Settings"])
    
    with tab_cache:
        render_cache_details_tab()
    
    # 3. TRACK CACHE IMPACT DURING RUN
    if st.button("Run Pipeline"):
        with cache_tracking_context(run_id) as tracker:
            # Profile
            profile = profile_dataset(file_path, run_id)
            tracker.record_profile_miss()  # or record_profile_hit()
            
            # STTM
            bronze_sttm = generate_bronze_sttm(...)
            tracker.record_sttm_miss()  # or record_sttm_hit()
            
            # ... rest of pipeline ...
        
        # 4. DISPLAY CACHE IMPACT
        render_cache_impact()

if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════════════════════════════════════
# CACHE INVALIDATION STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════════

# Manual invalidation (in settings/admin UI):

from core.caching import get_cache_manager

cache_mgr = get_cache_manager()

# Clear all cache
cache_mgr.clear_cache()

# Clear specific type
cache_mgr.clear_cache(cache_type="profile")
cache_mgr.clear_cache(cache_type="sttm")
cache_mgr.clear_cache(cache_type="llm")

# Clear old entries
cache_mgr.clear_cache(older_than_days=7)  # Clear entries older than 7 days

# Disable caching globally
cache_mgr.config.enabled = False


# ═══════════════════════════════════════════════════════════════════════════════
# CACHE STATISTICS & MONITORING
# ═══════════════════════════════════════════════════════════════════════════════

cache_mgr = get_cache_manager()
stats = cache_mgr.get_stats()

print(f"Cache enabled: {stats['enabled']}")
print(f"Total entries: {stats['total_entries']}")
print(f"Cache size: {stats['cache_dir_size_mb']:.2f} MB")

print(f"\nProfile cache:")
print(f"  Hits: {stats['profile']['hits']}")
print(f"  Misses: {stats['profile']['misses']}")
print(f"  Hit rate: {stats['profile']['hit_rate']:.1f}%")

print(f"\nSTTM cache:")
print(f"  Hits: {stats['sttm']['hits']}")
print(f"  Misses: {stats['sttm']['misses']}")
print(f"  Hit rate: {stats['sttm']['hit_rate']:.1f}%")

print(f"\nLLM cache:")
print(f"  Hits: {stats['llm']['hits']}")
print(f"  Misses: {stats['llm']['misses']}")
print(f"  Hit rate: {stats['llm']['hit_rate']:.1f}%")
