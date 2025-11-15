"""
自动发送消息处理模块 (已修正，可读取上下文)
"""

import logging
import random
import threading
from datetime import datetime, timedelta

logger = logging.getLogger('main')

class AutoSendHandler:
    def __init__(self, message_handler, config, listen_list):
        self.message_handler = message_handler
        self.config = config
        self.listen_list = listen_list
        
        # 计时器相关
        self.countdown_timer = None
        self.is_countdown_running = False
        self.countdown_end_time = None
        self.unanswered_count = 0
        self.last_chat_time = None

    def update_last_chat_time(self):
        """更新最后一次聊天时间"""
        self.last_chat_time = datetime.now()
        self.unanswered_count = 0
        logger.info(f"更新最后聊天时间: {self.last_chat_time}，重置未回复计数器为0")

    def is_quiet_time(self) -> bool:
        """检查当前是否在安静时间段内"""
        try:
            current_time = datetime.now().time()
            quiet_start = datetime.strptime(self.config.behavior.quiet_time.start, "%H:%M").time()
            quiet_end = datetime.strptime(self.config.behavior.quiet_time.end, "%H:%M").time()
            
            if quiet_start <= quiet_end:
                return quiet_start <= current_time <= quiet_end
            else:
                return current_time >= quiet_start or current_time <= quiet_end
        except Exception as e:
            logger.error(f"检查安静时间出错: {str(e)}")
            return False

    def get_random_countdown_time(self):
        """获取随机倒计时时间"""
        #【修正】确保能正确读取新版config.json的层级
        try:
            min_seconds = int(self.config.behavior.auto_message.countdown.min_hours * 3600)
            max_seconds = int(self.config.behavior.auto_message.countdown.max_hours * 3600)
        except AttributeError:
             # 兼容老版config.json的层级
            min_seconds = int(self.config.behavior.auto_message.min_hours * 3600)
            max_seconds = int(self.config.behavior.auto_message.max_hours * 3600)
        return random.uniform(min_seconds, max_seconds)

    #【关键改动】重构 auto_send_message 方法
    def auto_send_message(self):
        """自动发送消息"""
        if self.is_quiet_time():
            logger.info("当前处于安静时间，跳过自动发送消息")
            self.start_countdown()
            return
            
        if self.listen_list:
            # 随机选择一个要主动发送消息的用户
            target_user_id = random.choice(self.listen_list)
            
            # 1. 从配置文件读取指令，如果为空则使用更简洁的默认指令
            custom_instruction = self.config.behavior.auto_message.content.strip()
            if custom_instruction:
                content_to_send = custom_instruction
                logger.info(f"使用配置文件中的自定义主动消息指令: '{content_to_send}'")
            else:
                # 如果配置文件内容为空，则使用一个非常中性的内部指令，让AI自行发挥
                content_to_send = "【系统指令】请你作为当前角色，完全根据上下文（包括时间、记忆和人设），主动向用户发起一段符合情境的对话。"
                logger.info("配置文件中的主动消息指令为空，使用默认内部指令让AI自行发挥。")

            logger.info(f"准备向 {target_user_id} 自动发送消息...")
            
            try:
                # 2. 【核心修正】使用目标用户的ID作为 sender_name 和 username
                #    这样 MessageHandler 就能加载到正确的上下文和记忆了！
                self.message_handler.add_to_queue(
                    chat_id=target_user_id,
                    content=content_to_send,
                    sender_name=target_user_id, # <-- 修正
                    username=target_user_id,  # <-- 修正
                    is_group=False
                )
            except Exception as e:
                logger.error(f"自动发送消息失败: {str(e)}")
            finally:
                # 无论成功失败，都重新开始下一轮倒计时
                self.start_countdown()
        else:
            logger.warning("监听列表为空，无法自动发送消息。")
            self.start_countdown()

    def start_countdown(self):
        """开始新的倒计时"""
        if self.countdown_timer:
            self.countdown_timer.cancel()
        
        countdown_seconds = self.get_random_countdown_time()
        self.countdown_end_time = datetime.now() + timedelta(seconds=countdown_seconds)
        logger.info(f"开始新的倒计时: {countdown_seconds/3600:.2f}小时")
        
        self.countdown_timer = threading.Timer(countdown_seconds, self.auto_send_message)
        self.countdown_timer.daemon = True
        self.countdown_timer.start()
        self.is_countdown_running = True

    def stop(self):
        """停止自动发送消息"""
        if self.countdown_timer:
            self.countdown_timer.cancel()
            self.countdown_timer = None
        self.is_countdown_running = False
        logger.info("自动发送消息已停止")
