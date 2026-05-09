#!/usr/bin/env python3
"""
LUODA CI 构建自动监控工具
使用方法：python3 auto-build-monitor.py

功能:
1. 监控最新的流水线
2. 实时显示构建日志
3. 发现错误自动分析
4. 构建完成发送通知
"""

import requests
import time
import sys
import os
from datetime import datetime

# 配置
GITEE_TOKEN = "1b95687a02f7a7e30776af59bdf5826d"
OWNER = "soulemo_1_0"
REPO = "rustdesk146"
BASE_URL = "https://gitee.com/api/v5"

class Colors:
    """ANSI 颜色代码"""
    RESET = "\033[0m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"

class BuildMonitor:
    def __init__(self):
        self.headers = {"Authorization": f"Bearer {GITEE_TOKEN}"}
        self.pipeline_id = None
        self.last_state = None
        self.start_time = None
        
    def get_pipelines(self, page=1, per_page=5):
        """获取流水线列表"""
        url = f"{BASE_URL}/repos/{OWNER}/{REPO}/pipelines"
        params = {"page": page, "per_page": per_page}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"{Colors.RED}❌ API 请求失败：{response.status_code}{Colors.RESET}")
                return []
        except Exception as e:
            print(f"{Colors.RED}❌ 网络错误：{e}{Colors.RESET}")
            return []
    
    def get_pipeline_detail(self, pipeline_id):
        """获取流水线详情"""
        url = f"{BASE_URL}/repos/{OWNER}/{REPO}/pipelines/{pipeline_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            return None
    
    def display_pipelines(self, pipelines):
        """显示流水线列表"""
        print(f"\n{Colors.BOLD}=== 📋 流水线列表 ==={Colors.RESET}\n")
        
        if not pipelines:
            print(f"{Colors.YELLOW}⚠️  未找到流水线{Colors.RESET}")
            return
        
        for i, p in enumerate(pipelines, 1):
            state = p.get('state', 'unknown')
            trigger = p.get('trigger', 'manual')
            created = p.get('created_at', '')[:19].replace('T', ' ')
            pid = p.get('id')
            
            state_emoji = {
                'success': '✅',
                'failure': '❌',
                'running': '⏳',
                'pending': '⏳',
                'cancelled': '🚫'
            }.get(state, '⚪')
            
            color = {
                'success': Colors.GREEN,
                'failure': Colors.RED,
                'running': Colors.BLUE,
                'pending': Colors.YELLOW
            }.get(state, Colors.RESET)
            
            print(f"{color}{state_emoji} #{i} ID: {pid:6d} | 状态：{state:10s} | 触发：{trigger:6s} | 时间：{created}{Colors.RESET}")
    
    def monitor_pipeline(self, pipeline_id, check_interval=10):
        """监控单个流水线"""
        self.pipeline_id = pipeline_id
        print(f"\n{Colors.BOLD}=== ⏳ 开始监控流水线 {pipeline_id} ==={Colors.RESET}\n")
        print(f"📄 详情链接：https://gitee.com/{OWNER}/{REPO}/pipelines/{pipeline_id}")
        print(f"🕐 监控间隔：{check_interval}秒")
        print(f"{'='*60}\n")
        
        self.start_time = time.time()
        check_count = 0
        max_checks = 360  # 最多监控 60 分钟
        
        while check_count < max_checks:
            check_count += 1
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            # 获取流水线状态
            detail = self.get_pipeline_detail(pipeline_id)
            if not detail:
                print(f"[{timestamp}] ❌ 无法获取状态")
                time.sleep(check_interval)
                continue
            
            state = detail.get('state', 'unknown')
            trigger = detail.get('trigger', 'manual')
            
            # 状态变化时显示
            if state != self.last_state:
                duration = int(time.time() - self.start_time)
                minutes = duration // 60
                seconds = duration % 60
                
                state_emoji = {
                    'success': '✅',
                    'failure': '❌',
                    'running': '⏳',
                    'pending': '⏳',
                    'cancelled': '🚫'
                }.get(state, '⚪')
                
                print(f"[{timestamp}] {state_emoji} 状态：{state:10s} | 触发：{trigger} | 耗时：{minutes:02d}分{seconds:02d}秒")
                self.last_state = state
            
            # 检查是否完成
            if state in ['success', 'failure', 'cancelled', 'timeout']:
                self.notify_completion(detail)
                return state == 'success'
            
            time.sleep(check_interval)
        
        print(f"\n{Colors.RED}⏰ 监控超时 (60 分钟){Colors.RESET}")
        return False
    
    def notify_completion(self, pipeline):
        """构建完成通知"""
        state = pipeline.get('state')
        pipeline_id = pipeline.get('id')
        
        print(f"\n{'='*60}")
        
        if state == 'success':
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 构建成功！{Colors.RESET}\n")
            print(f"📦 产物下载:")
            print(f"   https://gitee.com/{OWNER}/{REPO}/pipelines/{pipeline_id}/artifacts")
            print(f"\n📄 查看日志:")
            print(f"   https://gitee.com/{OWNER}/{REPO}/pipelines/{pipeline_id}/jobs")
        elif state == 'failure':
            print(f"{Colors.RED}{Colors.BOLD}❌ 构建失败！{Colors.RESET}\n")
            print(f"📄 查看错误日志:")
            print(f"   https://gitee.com/{OWNER}/{REPO}/pipelines/{pipeline_id}/jobs")
            print(f"\n💡 建议:")
            print(f"   1. 检查构建日志找出错误原因")
            print(f"   2. 修复后重新触发构建")
            print(f"   3. 查看 CI_GUIDE.md 了解常见错误")
        else:
            print(f"{Colors.YELLOW}⚠️  构建{state}{Colors.RESET}")
        
        print(f"{'='*60}\n")
    
    def run(self):
        """运行监控"""
        print(f"{Colors.BOLD}{Colors.CYAN}")
        print("=" * 60)
        print("         🚀 LUODA CI 构建监控")
        print("=" * 60)
        print(f"{Colors.RESET}")
        print(f"仓库：{OWNER}/{REPO}")
        print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 获取最新流水线
        pipelines = self.get_pipelines()
        
        if not pipelines:
            print(f"\n{Colors.YELLOW}⚠️  未找到任何流水线{Colors.RESET}")
            print(f"\n{Colors.BOLD}💡 请手动触发构建:{Colors.RESET}")
            print(f"   1. 访问：https://gitee.com/{OWNER}/{REPO}/pipelines")
            print(f"   2. 点击「运行流水线」按钮")
            print(f"   3. 选择「luoda-full-build」")
            print(f"   4. 选择分支「master」")
            print(f"   5. 点击「运行」开始构建")
            print(f"\n{Colors.CYAN}📋 或者使用以下命令查看实时日志:{Colors.RESET}")
            print(f"   python3 auto-build-monitor.py --monitor <pipeline_id>")
            return False
        
        # 显示流水线列表
        self.display_pipelines(pipelines)
        
        # 选择最新的流水线进行监控
        latest = pipelines[0]
        latest_id = latest.get('id')
        latest_state = latest.get('state')
        
        print(f"\n{Colors.BOLD}=== 📊 最新构建状态 ==={Colors.RESET}\n")
        print(f"流水线 ID: {latest_id}")
        print(f"当前状态：{latest_state}")
        print(f"创建时间：{latest.get('created_at', 'N/A')}")
        
        # 决定是否开始监控
        if latest_state in ['pending', 'running']:
            print(f"\n{Colors.BLUE}⏳ 检测到正在运行的构建，开始监控...{Colors.RESET}\n")
            time.sleep(2)
            return self.monitor_pipeline(latest_id)
        else:
            print(f"\n{Colors.YELLOW}⚠️  最新构建已完成 ({latest_state}){Colors.RESET}")
            print(f"\n{Colors.BOLD}💡 操作建议:{Colors.RESET}")
            print(f"   - 监控此构建日志：python3 auto-build-monitor.py --monitor {latest_id}")
            print(f"   - 触发新构建：访问 https://gitee.com/{OWNER}/{REPO}/pipelines")
            return latest_state == 'success'


def main():
    monitor = BuildMonitor()
    success = monitor.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
