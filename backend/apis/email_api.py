from flask import Blueprint, request, jsonify
from backend.utils.email.imap import IMAPMailHandler
from backend.db.models import Email, db
import json
import traceback
import time

email_api = Blueprint('email_api', __name__)

@email_api.route('/add', methods=['POST'])
def add_email():
    """添加单个邮箱账户"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        server = data.get('server')
        port = data.get('port')
        use_ssl = data.get('use_ssl', True)  # 默认使用SSL
        
        # 验证数据
        if not username or not password:
            return jsonify({'success': False, 'message': '邮箱和密码不能为空'}), 400
        
        # 检查是否已存在
        existing = Email.query.filter_by(username=username).first()
        if existing:
            return jsonify({'success': False, 'message': '该邮箱已存在'}), 400
        
        # 测试连接
        try:
            if '@' in username and not server:
                domain = username.split('@')[1].lower()
                handler = IMAPMailHandler(None, username, password, use_ssl=use_ssl, port=port)
            else:
                handler = IMAPMailHandler(server, username, password, use_ssl=use_ssl, port=port)
            
            if not handler.connect():
                return jsonify({'success': False, 'message': f'连接失败: {handler.error}'}), 400
            
            handler.close()
        except Exception as e:
            return jsonify({'success': False, 'message': f'连接测试失败: {str(e)}'}), 400
        
        # 保存到数据库
        new_email = Email(
            username=username,
            password=password,
            type='imap',
            status='active'
        )
        
        if server:
            new_email.server = server
            
        if port:
            new_email.port = port
            
        # 保存SSL选项
        new_email.use_ssl = use_ssl
        
        db.session.add(new_email)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '邮箱添加成功',
            'email': {
                'id': new_email.id,
                'username': new_email.username,
                'type': new_email.type,
                'status': new_email.status,
                'server': new_email.server,
                'port': new_email.port,
                'use_ssl': new_email.use_ssl,
                'created_at': new_email.created_at.isoformat() if new_email.created_at else None
            }
        })
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'添加邮箱失败: {str(e)}'}), 500

@email_api.route('/import', methods=['POST'])
def import_emails():
    """批量导入邮箱账户"""
    try:
        data = request.json
        emails_data = data.get('emails', '')
        
        if not emails_data:
            return jsonify({'success': False, 'message': '没有提供邮箱数据'}), 400
        
        # 解析批量导入数据
        emails_list = IMAPMailHandler.parse_imap_list(emails_data)
        
        if not emails_list:
            return jsonify({'success': False, 'message': '无有效邮箱数据'}), 400
        
        results = []
        success_count = 0
        fail_count = 0
        
        for email_data in emails_list:
            username = email_data.get('username')
            password = email_data.get('password')
            server = email_data.get('server')
            port = email_data.get('port')
            use_ssl = email_data.get('use_ssl', True)
            
            # 检查是否已存在
            existing = Email.query.filter_by(username=username).first()
            if existing:
                results.append({
                    'username': username,
                    'success': False,
                    'message': '该邮箱已存在'
                })
                fail_count += 1
                continue
                
            # 测试连接
            try:
                if '@' in username and not server:
                    handler = IMAPMailHandler(None, username, password, use_ssl=use_ssl, port=port)
                else:
                    handler = IMAPMailHandler(server, username, password, use_ssl=use_ssl, port=port)
                
                if not handler.connect():
                    results.append({
                        'username': username,
                        'success': False,
                        'message': f'连接失败: {handler.error}'
                    })
                    fail_count += 1
                    continue
                    
                handler.close()
            except Exception as e:
                results.append({
                    'username': username,
                    'success': False,
                    'message': f'连接测试失败: {str(e)}'
                })
                fail_count += 1
                continue
                
            # 保存到数据库
            new_email = Email(
                username=username,
                password=password,
                type='imap',
                status='active'
            )
            
            if server:
                new_email.server = server
                
            if port:
                new_email.port = port
                
            # 保存SSL选项
            new_email.use_ssl = use_ssl
            
            db.session.add(new_email)
            
            results.append({
                'username': username,
                'success': True,
                'message': '添加成功'
            })
            success_count += 1
            
            # 每10个提交一次，避免长时间不提交
            if len(results) % 10 == 0:
                db.session.commit()
        
        # 最后提交
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'导入完成: 成功 {success_count} 个, 失败 {fail_count} 个',
            'results': results
        })
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'导入邮箱失败: {str(e)}'}), 500

@email_api.route('/list', methods=['GET'])
def list_emails():
    """获取所有邮箱账户"""
    try:
        emails = Email.query.all()
        result = []
        
        for email in emails:
            result.append({
                'id': email.id,
                'username': email.username,
                'type': email.type,
                'status': email.status,
                'server': email.server,
                'port': email.port,
                'use_ssl': email.use_ssl,
                'created_at': email.created_at.isoformat() if email.created_at else None
            })
            
        return jsonify({
            'success': True,
            'emails': result
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取邮箱列表失败: {str(e)}'}), 500

@email_api.route('/delete/<int:email_id>', methods=['DELETE'])
def delete_email(email_id):
    """删除邮箱账户"""
    try:
        email = Email.query.get(email_id)
        if not email:
            return jsonify({'success': False, 'message': '邮箱不存在'}), 404
            
        db.session.delete(email)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '邮箱删除成功'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'删除邮箱失败: {str(e)}'}), 500

@email_api.route('/test', methods=['POST'])
def test_connection():
    """测试邮箱连接"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        server = data.get('server')
        port = data.get('port')
        use_ssl = data.get('use_ssl', True)
        
        # 验证数据
        if not username or not password:
            return jsonify({'success': False, 'message': '邮箱和密码不能为空'}), 400
        
        # 测试连接
        try:
            if '@' in username and not server:
                handler = IMAPMailHandler(None, username, password, use_ssl=use_ssl, port=port)
            else:
                handler = IMAPMailHandler(server, username, password, use_ssl=use_ssl, port=port)
            
            start_time = time.time()
            connect_result = handler.connect()
            connect_time = time.time() - start_time
            
            if not connect_result:
                return jsonify({
                    'success': False, 
                    'message': f'连接失败: {handler.error}'
                }), 400
            
            # 测试获取文件夹
            start_time = time.time()
            folders = handler.get_folders()
            folders_time = time.time() - start_time
            
            handler.close()
            
            return jsonify({
                'success': True,
                'message': '连接测试成功',
                'folders': folders,
                'stats': {
                    'connect_time': round(connect_time, 2),
                    'folders_time': round(folders_time, 2),
                    'folders_count': len(folders)
                }
            })
        except Exception as e:
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'连接测试失败: {str(e)}'}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'测试连接失败: {str(e)}'}), 500

@email_api.route('/fetch/<int:email_id>', methods=['GET'])
def fetch_emails(email_id):
    """获取指定邮箱的邮件"""
    try:
        email = Email.query.get(email_id)
        if not email:
            return jsonify({'success': False, 'message': '邮箱不存在'}), 404
        
        folder = request.args.get('folder', 'INBOX')
        limit = request.args.get('limit', 100, type=int)
        
        # 连接IMAP服务器
        handler = IMAPMailHandler(
            email.server, 
            email.username, 
            email.password, 
            use_ssl=email.use_ssl, 
            port=email.port
        )
        
        if not handler.connect():
            return jsonify({
                'success': False, 
                'message': f'连接失败: {handler.error}'
            }), 400
        
        # 获取邮件
        messages = handler.get_messages(folder=folder, limit=limit)
        handler.close()
        
        return jsonify({
            'success': True,
            'messages': messages,
            'count': len(messages)
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'获取邮件失败: {str(e)}'}), 500 