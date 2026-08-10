"""
实时检查邮件的优化功能模块
"""

import logging
import time
import threading
import concurrent.futures
from datetime import datetime, timedelta
from .common import normalize_check_time

# 创建日志记录器
logger = logging.getLogger(__name__)

class RealTimeChecker:
    """实时邮件检查器类，用于优化实时邮件检查的生命周期"""
    
    def __init__(self, db, email_processor):
        """初始化实时邮件检查器
        
        Args:
            db: 数据库对象
            email_processor: 邮件处理器对象
        """
        self.db = db
        self.email_processor = email_processor
        self.running = False
        self.thread = None
        self.check_interval = 60  # 默认检查间隔为60秒
        self.last_check_time = {}  # 记录每个邮箱的最后检查时间
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    
    def start(self, check_interval=60):
        """启动实时邮件检查
        
        Args:
            check_interval: 检查间隔，单位为秒
        
        Returns:
            启动是否成功
        """
        if self.running:
            logger.warning("实时邮件检查已在运行")
            return False
        
        self.check_interval = max(check_interval, 30)  # 最小检查间隔为30秒
        self.running = True
        self.thread = threading.Thread(
            target=self._check_loop,
            daemon=True
        )
        self.thread.start()
        logger.info(f"实时邮件检查已启动，检查间隔: {self.check_interval}秒")
        return True
    
    def stop(self):
        """停止实时邮件检查
        
        Returns:
            停止是否成功
        """
        if not self.running:
            logger.warning("实时邮件检查未在运行")
            return False
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            logger.info("实时邮件检查已停止")
        return True
    
    def _check_loop(self):
        """实时邮件检查循环"""
        batch_size = 10  # 每批处理的邮箱数量
        
        while self.running:
            try:
                # 获取所有需要实时检查的邮箱
                users = self.db.get_users_with_realtime_check()
                if not users:
                    logger.info("没有启用实时检查的用户")
                    time.sleep(self.check_interval)
                    continue
                
                # 对每个用户进行处理
                for user in users:
                    if not self.running:
                        break
                    
                    try:
                        # 获取用户的所有邮箱
                        email_accounts = self.db.get_user_emails(user['id'])
                        
                        # 处理每个邮箱
                        for account in email_accounts:
                            if not self.running or self.email_processor.is_email_being_processed(account['id']):
                                continue
                            
                            # 提交检查任务
                            self._submit_check_task(account, user['id'])
                            
                            # 每处理一个邮箱等待1秒，避免过度占用资源
                            time.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"处理用户 {user.get('username', user['id'])} 的邮箱时出错: {str(e)}")
                
                # 等待下一次检查周期
                for _ in range(self.check_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"实时邮件检查出错: {str(e)}")
                time.sleep(self.check_interval)
    
    def _submit_check_task(self, account, user_id):
        """提交邮箱检查任务
        
        Args:
            account: 邮箱账户信息
            user_id: 用户ID
        """
        try:
            # 检查距离上次检查是否已经超过一定时间
            account_id = account['id']
            current_time = datetime.now()
            
            # 获取数据库中记录的最后检查时间
            last_check_time = account.get('last_check_time')
            
            # 如果数据库中没有最后检查时间，则使用内存中记录的时间
            if not last_check_time and account_id in self.last_check_time:
                last_check_time = self.last_check_time[account_id]
            
            # 标准化处理last_check_time
            last_check_time = normalize_check_time(last_check_time)
            
            # 如果有最后检查时间，且距离当前时间小于检查间隔的一半，则跳过
            if last_check_time and (current_time - last_check_time).total_seconds() < self.check_interval / 2:
                logger.debug(f"邮箱 {account['email']} 最近已检查，跳过本次检查")
                return
            
            # 创建进度回调
            def progress_callback(progress, message):
                logger.info(f"邮箱 ID {account_id} 处理进度: {progress}%, 消息: {message}")
                # 在这里可以添加WebSocket推送进度的代码
            
            # 提交到实时线程池
            future = self.email_processor.realtime_thread_pool.submit(
                self.email_processor._check_email_task,
                account,
                progress_callback
            )
            
            # 更新内存中的最后检查时间
            self.last_check_time[account_id] = current_time
            
            logger.info(f"已为邮箱 {account['email']} 提交检查任务")
            
        except Exception as e:
            logger.error(f"提交邮箱 {account.get('email', account_id)} 检查任务失败: {str(e)}") 