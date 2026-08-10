import json
import asyncio
import logging
import websockets
from websockets.exceptions import ConnectionClosed
import os
import jwt

logger = logging.getLogger('websocket_handler')

class WebSocketHandler:
    def __init__(self, host='0.0.0.0', port=8765):
        self.host = host
        self.port = port
        self.connections = set()
        self.email_processor = None
        self.db = None
        self.connected_clients = {}
    
    def set_dependencies(self, db, email_processor):
        """设置依赖的数据库和邮件处理器"""
        self.db = db
        self.email_processor = email_processor
    
    async def register(self, websocket):
        """注册新的WebSocket连接"""
        self.connections.add(websocket)
        logger.info(f"New client connected. Total connections: {len(self.connections)}")
    
    async def authenticate_client(self, websocket, user_info):
        """保存客户端认证信息"""
        self.connected_clients[websocket] = user_info
        logger.info(f"Client authenticated: {user_info.get('username', 'unknown')}")
    
    async def unregister(self, websocket):
        """注销WebSocket连接"""
        self.connections.remove(websocket)
        # 清除客户端信息
        if websocket in self.connected_clients:
            del self.connected_clients[websocket]
        logger.info(f"Client disconnected. Total connections: {len(self.connections)}")
    
    async def broadcast(self, message):
        """向所有连接的客户端广播消息"""
        if not self.connections:
            return
        
        message_str = json.dumps(message)
        await asyncio.gather(
            *[connection.send(message_str) for connection in self.connections],
            return_exceptions=True
        )
    
    async def send_to_client(self, websocket, message):
        """发送消息给特定客户端"""
        await websocket.send(json.dumps(message))
    
    async def handle_message(self, websocket, message_str):
        """处理客户端消息"""
        try:
            message = json.loads(message_str)
            action = message.get('action')
            
            if action == 'get_all_emails':
                await self.handle_get_all_emails(websocket)
            
            elif action == 'add_email':
                email = message.get('email')
                password = message.get('password')
                client_id = message.get('client_id')
                refresh_token = message.get('refresh_token')
                mail_type = message.get('mail_type', 'outlook')
                
                if mail_type == 'outlook':
                    try:
                        await self.handle_add_email(websocket, email, password, client_id, refresh_token, mail_type)
                    except Exception as e:
                        logger.error(f"添加Outlook邮箱时出错: {str(e)}")
                        await self.send_to_client(websocket, {
                            'type': 'error',
                            'message': f'添加Outlook邮箱时出错: {str(e)}'
                        })
                elif mail_type == 'imap':
                    server = message.get('server')
                    port = message.get('port', 993)
                    use_ssl = message.get('use_ssl', True)
                    try:
                        await self.handle_add_imap_email(websocket, email, password, server, port, use_ssl)
                    except Exception as e:
                        logger.error(f"添加IMAP邮箱时出错: {str(e)}")
                        await self.send_to_client(websocket, {
                            'type': 'error',
                            'message': f'添加IMAP邮箱时出错: {str(e)}'
                        })
                elif mail_type == 'gmail':
                    try:
                        await self.handle_add_gmail_email(websocket, email, password)
                    except Exception as e:
                        logger.error(f"添加Gmail邮箱时出错: {str(e)}")
                        await self.send_to_client(websocket, {
                            'type': 'error',
                            'message': f'添加Gmail邮箱时出错: {str(e)}'
                        })
                elif mail_type == 'qq':
                    try:
                        await self.handle_add_qq_email(websocket, email, password)
                    except Exception as e:
                        logger.error(f"添加QQ邮箱时出错: {str(e)}")
                        await self.send_to_client(websocket, {
                            'type': 'error',
                            'message': f'添加QQ邮箱时出错: {str(e)}'
                        })
                else:
                    await self.send_to_client(websocket, {
                        'type': 'error',
                        'message': f'不支持的邮箱类型: {mail_type}'
                    })
                    return
            
            elif action == 'delete_emails':
                email_ids = message.get('email_ids', [])
                await self.handle_delete_emails(websocket, email_ids)
            
            elif action == 'check_emails':
                email_ids = message.get('email_ids', [])
                await self.handle_check_emails(websocket, email_ids)
            
            elif action == 'get_mail_records':
                email_id = message.get('email_id')
                await self.handle_get_mail_records(websocket, email_id)
            
            elif action == 'import_emails':
                data = message.get('data', [])
                mail_type = message.get('mail_type', 'outlook')
                await self.handle_import_emails(websocket, data, mail_type)
            
            else:
                await self.send_to_client(websocket, {
                    'type': 'error',
                    'message': f'未知的操作: {action}'
                })
        except json.JSONDecodeError:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': '无效的JSON格式'
            })
        except Exception as e:
            logger.error(f"处理消息时出错: {str(e)}")
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': f'处理消息时出错: {str(e)}'
            })
    
    async def handle_get_all_emails(self, websocket):
        """处理获取所有邮箱的请求"""
        emails = self.db.get_all_emails()
        # 转换为可序列化的字典列表
        emails_list = [dict(email) for email in emails]
        await self.send_to_client(websocket, {
            'type': 'emails_list',
            'data': emails_list
        })
    
    async def handle_add_email(self, websocket, email, password, client_id, refresh_token, mail_type='outlook'):
        """处理添加邮箱的请求"""
        # 添加邮箱到数据库
        success = self.db.add_email(email, password, client_id, refresh_token, mail_type)
        
        if success:
            await self.send_to_client(websocket, {
                'type': 'success',
                'message': f'Email {email} added successfully'
            })
            
            # 通知所有客户端更新
            await self.broadcast({
                'type': 'email_added',
                'email': email
            })
        else:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': f'Email {email} already exists or could not be added'
            })
    
    async def handle_delete_emails(self, websocket, email_ids):
        """处理删除邮箱的请求"""
        if not email_ids:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': 'No email IDs provided'
            })
            return
        
        # 获取正在处理的邮箱
        processing_ids = []
        for email_id in email_ids:
            if self.email_processor.is_email_being_processed(email_id):
                processing_ids.append(email_id)
        
        # 停止正在处理的邮箱
        for email_id in processing_ids:
            self.email_processor.stop_processing(email_id)
        
        # 删除邮箱
        self.db.delete_emails(email_ids)
        
        await self.send_to_client(websocket, {
            'type': 'success',
            'message': f'Deleted {len(email_ids)} emails'
        })
        
        # 通知所有客户端更新
        await self.broadcast({
            'type': 'emails_deleted',
            'email_ids': email_ids
        })
    
    async def handle_check_emails(self, websocket, email_ids):
        """处理检查邮件的请求"""
        if not email_ids:
            # 如果没有提供 ID，则获取所有邮箱
            emails = self.db.get_all_emails()
            email_ids = [email['id'] for email in emails]
        
        if not email_ids:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': 'No emails found'
            })
            return
        
        # 定义进度回调
        def progress_callback(email_id, progress, message):
            asyncio.run_coroutine_threadsafe(
                self.broadcast({
                    'type': 'check_progress',
                    'email_id': email_id,
                    'progress': progress,
                    'message': message
                }),
                asyncio.get_event_loop()
            )
        
        # 启动邮件检查线程
        self.email_processor.check_emails(email_ids, progress_callback)
        
        await self.send_to_client(websocket, {
            'type': 'info',
            'message': f'Started checking {len(email_ids)} emails'
        })
    
    async def handle_get_mail_records(self, websocket, email_id):
        """处理获取邮件记录的请求"""
        if not email_id:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': 'Email ID is required'
            })
            return
        
        mail_records = self.db.get_mail_records(email_id)
        mail_records_list = [dict(record) for record in mail_records]
        
        await self.send_to_client(websocket, {
            'type': 'mail_records',
            'email_id': email_id,
            'data': mail_records_list
        })
    
    async def handle_import_emails(self, websocket, data, mail_type='outlook'):
        """处理批量导入邮箱的请求"""
        # 获取用户信息
        user_info = self.connected_clients.get(websocket)
        if not user_info:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': 'Unauthorized'
            })
            return
        
        user_id = user_info.get('id')
        if not user_id:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': 'Invalid user information'
            })
            return
        
        # 处理新旧两种格式
        if isinstance(data, dict):
            import_data = data.get('data', '')
            mail_type = data.get('mail_type', 'outlook')
        else:
            import_data = data
        
        if not import_data:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': 'No data provided'
            })
            return
        
        lines = import_data.strip().split('\n')
        success_count = 0
        failed_lines = []
        
        for line_number, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            parts = line.split('----')
            if len(parts) != 4:
                failed_lines.append((line_number, line, 'Invalid format'))
                continue
            
            email, password, client_id, refresh_token = parts
            if not all([email, password, client_id, refresh_token]):
                failed_lines.append((line_number, line, 'Missing required fields'))
                continue
            
            try:
                success = self.db.add_email(user_id, email, password, client_id, refresh_token, mail_type)
                if success:
                    success_count += 1
                else:
                    failed_lines.append((line_number, line, 'Email already exists'))
            except Exception as e:
                logger.error(f"Error adding email: {str(e)}")
                failed_lines.append((line_number, line, f'Error: {str(e)}'))
        
        result = {
            'type': 'import_result',
            'total': len(lines),
            'success': success_count,
            'failed': len(failed_lines),
            'failed_details': [
                {'line': line_num, 'content': content, 'reason': reason}
                for line_num, content, reason in failed_lines
            ]
        }
        
        await self.send_to_client(websocket, result)
        
        if success_count > 0:
            # 通知所有客户端更新
            await self.broadcast({
                'type': 'emails_imported',
                'count': success_count
            })
            
            # 记录日志
            logger.info(f"User {user_id} imported {success_count} emails. Failed: {len(failed_lines)}")
    
    async def handle_add_imap_email(self, websocket, email, password, server, port, use_ssl=True):
        """处理添加IMAP邮箱的请求"""
        # 验证参数
        if not email or not password:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': '邮箱地址和密码不能为空'
            })
            return
        
        # 获取用户信息
        user_info = self.connected_clients.get(websocket)
        if not user_info:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': '未授权，请先进行认证'
            })
            return
        
        user_id = user_info.get('id')
        if not user_id:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': '用户信息无效'
            })
            return
        
        # 检查邮箱是否已存在
        existing_emails = self.db.get_emails_by_user_id(user_id)
        for existing in existing_emails:
            if existing['email'] == email:
                await self.send_to_client(websocket, {
                    'type': 'error',
                    'message': f'邮箱 {email} 已存在'
                })
                return
        
        try:
            # 添加邮箱到数据库
            email_id = self.db.add_email(
                user_id=user_id,
                email=email,
                password=password,
                mail_type='imap',
                server=server,
                port=port,
                use_ssl=use_ssl
            )
            
            if email_id:
                # 通知客户端添加成功
                await self.send_to_client(websocket, {
                    'type': 'email_added',
                    'message': f'邮箱 {email} 添加成功'
                })
                
                # 发送更新后的邮箱列表
                emails = self.db.get_all_emails(user_id)
                emails_list = [dict(email) for email in emails]
                await self.send_to_client(websocket, {
                    'type': 'emails_list',
                    'data': emails_list
                })
            else:
                await self.send_to_client(websocket, {
                    'type': 'error',
                    'message': f'添加邮箱 {email} 失败'
                })
        except Exception as e:
            logging.error(f"添加邮箱出错: {str(e)}")
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': f'添加邮箱时出错: {str(e)}'
            })
    
    async def handle_add_gmail_email(self, websocket, email, password):
        """处理添加Gmail邮箱的请求"""
        # 验证参数
        if not email or not password:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': '邮箱地址和密码不能为空'
            })
            return
        
        # 获取用户信息
        user_info = self.connected_clients.get(websocket)
        if not user_info:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': '未授权，请先进行认证'
            })
            return
        
        user_id = user_info.get('id')
        if not user_id:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': '用户信息无效'
            })
            return
        
        # 检查邮箱是否已存在
        existing_emails = self.db.get_emails_by_user_id(user_id)
        for existing in existing_emails:
            if existing['email'] == email:
                await self.send_to_client(websocket, {
                    'type': 'error',
                    'message': f'邮箱 {email} 已存在'
                })
                return
        
        try:
            # 添加邮箱到数据库
            email_id = self.db.add_email(
                user_id=user_id,
                email=email,
                password=password,
                mail_type='gmail',
                server='imap.gmail.com',
                port=993,
                use_ssl=True
            )
            
            if email_id:
                # 通知客户端添加成功
                await self.send_to_client(websocket, {
                    'type': 'email_added',
                    'message': f'邮箱 {email} 添加成功'
                })
                
                # 发送更新后的邮箱列表
                emails = self.db.get_all_emails(user_id)
                emails_list = [dict(email) for email in emails]
                await self.send_to_client(websocket, {
                    'type': 'emails_list',
                    'data': emails_list
                })
            else:
                await self.send_to_client(websocket, {
                    'type': 'error',
                    'message': f'邮箱 {email} 添加失败，可能已存在'
                })
        except Exception as e:
            logger.error(f"添加Gmail邮箱时出错: {str(e)}")
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': f'添加Gmail邮箱时出错: {str(e)}'
            })

    async def handle_add_qq_email(self, websocket, email, password):
        """处理添加QQ邮箱的请求"""
        # 验证参数
        if not email or not password:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': '邮箱地址和密码不能为空'
            })
            return
        
        # 获取用户信息
        user_info = self.connected_clients.get(websocket)
        if not user_info:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': '未授权，请先进行认证'
            })
            return
        
        user_id = user_info.get('id')
        if not user_id:
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': '用户信息无效'
            })
            return
        
        # 检查邮箱是否已存在
        existing_emails = self.db.get_emails_by_user_id(user_id)
        for existing in existing_emails:
            if existing['email'] == email:
                await self.send_to_client(websocket, {
                    'type': 'error',
                    'message': f'邮箱 {email} 已存在'
                })
                return
        
        try:
            # 添加邮箱到数据库
            email_id = self.db.add_email(
                user_id=user_id,
                email=email,
                password=password,
                mail_type='qq',
                server='imap.qq.com',
                port=993,
                use_ssl=True
            )
            
            if email_id:
                # 通知客户端添加成功
                await self.send_to_client(websocket, {
                    'type': 'email_added',
                    'message': f'邮箱 {email} 添加成功'
                })
                
                # 发送更新后的邮箱列表
                emails = self.db.get_all_emails(user_id)
                emails_list = [dict(email) for email in emails]
                await self.send_to_client(websocket, {
                    'type': 'emails_list',
                    'data': emails_list
                })
            else:
                await self.send_to_client(websocket, {
                    'type': 'error',
                    'message': f'邮箱 {email} 添加失败，可能已存在'
                })
        except Exception as e:
            logger.error(f"添加QQ邮箱时出错: {str(e)}")
            await self.send_to_client(websocket, {
                'type': 'error',
                'message': f'添加QQ邮箱时出错: {str(e)}'
            })
    
    async def handle_client(self, websocket, path):
        """处理客户端连接"""
        await self.register(websocket)
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except ConnectionClosed:
            logger.info("Client connection closed")
        finally:
            await self.unregister(websocket)
    
    async def start_server(self):
        """启动WebSocket服务器"""
        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")
        async with websockets.serve(self.handle_client, self.host, self.port):
            await asyncio.Future()  # 运行直到被取消
    
    def run(self):
        """运行WebSocket服务器"""
        if not self.db or not self.email_processor:
            raise ValueError("Database and EmailProcessor must be set before running")
        
        asyncio.run(self.start_server())
    
    def validate_token(self, token):
        """验证JWT Token"""
        if not token:
            return None
            
        try:
            # 解码JWT令牌
            import jwt
            
            # 使用环境变量中的JWT密钥，默认使用固定值
            jwt_secret = os.environ.get('JWT_SECRET_KEY', 'huohuo_email_secret_key')
            
            # 解码JWT令牌
            data = jwt.decode(token, jwt_secret, algorithms=["HS256"])
            
            # 检查用户是否存在
            user = self.db.get_user_by_id(data['user_id'])
            if not user:
                return None
            
            # 返回完整的用户信息
            return {
                'id': user['id'],
                'username': user.get('username', 'unknown'),
                'is_admin': user.get('is_admin', False)
            }
        except jwt.ExpiredSignatureError:
            logger.warning("令牌已过期")
            return None
        except Exception as e:
            logger.error(f"令牌验证失败: {str(e)}")
            return None 