from datetime import datetime, timezone, timedelta

# Vietnam timezone UTC+7
VN_TZ = timezone(timedelta(hours=7))

def utc_to_vn(utc_dt):
    """Convert UTC datetime to Vietnam timezone"""
    if utc_dt is None:
        return None
    if utc_dt.tzinfo is None:
        # Assume UTC if no timezone info
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(VN_TZ)

def vn_now():
    """Get current time in Vietnam timezone (naive datetime)"""
    return datetime.now(VN_TZ).replace(tzinfo=None)

def vn_to_utc(vn_dt):
    """Convert Vietnam datetime to UTC for storage"""
    if vn_dt is None:
        return None
    if vn_dt.tzinfo is None:
        # Assume VN timezone
        vn_dt = vn_dt.replace(tzinfo=VN_TZ)
    return vn_dt.astimezone(timezone.utc).replace(tzinfo=None)

# ============================================
#  CACHE BUSTER
# ============================================
def versioned_static(filename):
    """Thêm version vào static URL để tránh cache"""
    from flask import url_for, current_app
    version = current_app.config.get('VERSION', '1.0')
    url = url_for('static', filename=filename)
    return f"{url}?v={version}"

def init_cache_buster(app):
    """Đăng ký cache buster với Flask"""
    app.jinja_env.globals['versioned_static'] = versioned_static
    print(f"✅ Cache buster OK (v{app.config.get('VERSION')})")