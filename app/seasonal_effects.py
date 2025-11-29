from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.decorators import role_required
from app.models import SeasonalEffectConfig
from app import db, csrf
import json

bp = Blueprint('seasonal_effects', __name__)
csrf.exempt(bp)

# Danh sách tất cả các trang có thể dùng
AVAILABLE_PAGES = [
    {'id': 'hub', 'name': 'Trang Chủ'},
    {'id': 'tasks', 'name': 'Nhiệm Vụ'},
    {'id': 'files', 'name': 'Tệp Tin'},
    {'id': 'notes', 'name': 'Ghi Chú'},
    {'id': 'salaries', 'name': 'Lương'},
    {'id': 'news', 'name': 'Tin Tức'},
    {'id': 'performance', 'name': 'Hiệu Suất'},
    {'id': 'employees', 'name': 'Nhân Viên'},
    {'id': 'all', 'name': 'Tất Cả Trang'},
]


@bp.route('/settings')
@login_required
@role_required(['director'])
def settings():
    """Trang cài đặt - CHỈ DIRECTOR"""
    return render_template('seasonal_effects/settings.html', available_pages=AVAILABLE_PAGES)


@bp.route('/api/get-config')
@login_required
def get_config():
    """Lấy config hiệu ứng - TẤT CẢ USER"""
    try:
        config = SeasonalEffectConfig.get_active_config()

        if config:
            return jsonify({
                'success': True,
                'config': config
            })

        # Config mặc định
        default_config = {
            'effects': {
                'snowfall': {
                    'active': False,
                    'duration': 0,
                    'intensity': 50,
                    'speed': 'medium',
                    'pages': ['all']
                },
                'fireworks': {
                    'active': False,
                    'duration': 0,
                    'frequency': 1500,
                    'intensity': 50,
                    'colors': ['#ff0000', '#ffd700', '#00ff00', '#0000ff', '#ff00ff'],
                    'pages': ['all']
                },
                'noel': {
                    'active': False,
                    'duration': 0,
                    'intensity': 50,
                    'pages': ['all']
                },
                'tet': {
                    'active': False,
                    'duration': 0,
                    'intensity': 50,
                    'pages': ['all']
                },
                'flags': {
                    'active': False,
                    'duration': 0,
                    'intensity': 50,
                    'pages': ['all']
                },
                'santa': {
                    'active': False,
                    'message': 'Chúc Mừng Giáng Sinh! 🎄',
                    'delay': 1000,
                    'sparkles': True,
                    'pages': ['all']
                }
            }
        }

        return jsonify({
            'success': True,
            'config': default_config
        })

    except Exception as e:
        print(f"❌ Error in get_config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/save-config', methods=['POST'])
@login_required
@role_required(['director'])
def save_config():
    """Lưu config - CHỈ DIRECTOR"""
    try:
        data = request.get_json()
        print(f"📥 Received data: {data}")

        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        if 'effects' not in data:
            return jsonify({
                'success': False,
                'error': 'Invalid config structure - missing effects key'
            }), 400

        config_record = SeasonalEffectConfig.query.first()

        if not config_record:
            print("📝 Creating new config record")
            config_record = SeasonalEffectConfig(
                updated_by=current_user.id
            )
            db.session.add(config_record)
        else:
            print(f"📝 Updating existing config record (ID: {config_record.id})")
            config_record.updated_by = current_user.id

        # Validate pages trong config - mặc định nếu không có
        for effect_name, effect_config in data.get('effects', {}).items():
            if 'pages' not in effect_config or not effect_config['pages']:
                effect_config['pages'] = ['all']

        config_record.set_config(data)
        db.session.commit()

        print("✅ Config saved successfully")

        return jsonify({
            'success': True,
            'message': 'Config saved successfully'
        })

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error saving config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/get-pages-list')
@login_required
@role_required(['director'])
def get_pages_list():
    """Lấy danh sách trang có sẵn"""
    return jsonify({
        'success': True,
        'pages': AVAILABLE_PAGES
    })


@bp.route('/api/check-should-show/<effect_name>')
@login_required
def check_should_show(effect_name):
    """Kiểm tra xem có nên hiển thị effect trên trang hiện tại"""
    try:
        current_page = request.args.get('page', 'hub')

        should_show = SeasonalEffectConfig.should_show_effect(effect_name, current_page)

        return jsonify({
            'success': True,
            'should_show': should_show,
            'effect': effect_name,
            'current_page': current_page
        })
    except Exception as e:
        print(f"❌ Error checking should_show: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500