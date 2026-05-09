#!/usr/bin/env python3
"""
GitHub Actions 构建监控工具
使用方法：python3 monitor-github-build.py --token YOUR_TOKEN

功能:
1. 实时监控构建状态
2. 自动获取构建日志
3. 发现错误自动分析
4. 构建完成通知
"""

import requests
import time
import sys
import os
from datetime import datetime

# 配置 - 请修改为你的信息
GITHUB_OWNER = "luoda2023"
GITHUB_REPO = "LUODA-RemoteDesktop"
GITHUB_TOKEN = "YOUR_GITHUB_TOKEN_HERE"  # 替换为你的 Token

class Colors:
    RESET = "\033[0m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"

class GitHubMonitor:
    def __init__(self, token, owner=GITHUB_OWNER, repo=GITHUB_REPO):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = f"https://api.github.com/repos/{owner}/{repo}"
        self.run_id = None
        self.last_status = None
        self.start_time = None
    
    def get_recent_run(self, status_filter=None):
        """获取最近的构建运行"""
        url = f"{self.base_url}/actions/runs"
        params = {"per_page": 10}
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code != 200:
            return None
        
        runs = response.json().get('workflow_runs', [])
        
        if status_filter:
            runs = [r for r in runs if r.get('status') == status_filter]
        
        return runs[0] if runs else None
    
    def get_run_status(self, run_id):
        """获取构建状态"""
        url = f"{self.base_url}/actions/runs/{run_id}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        return None
    
    def get_job_logs(self, run_id):
        """获取作业日志"""
        url = f"{self.base_url}/actions/runs/{run_id}/jobs"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            return []
        
        return response.json().get('jobs', [])
    
    def get_log_content(self, job_id):
        """获取单个作业的日志内容"""
        url = f"{self.base_url}/actions/jobs/{job_id}/logs"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.text
        return ""
    
    def monitor_run(self, run_id, check_interval=10):
        """监控单个构建"""
        self.run_id = run_id
        print(f"\n{Colors.BOLD}=== ⏳ 开始监控构建 {run_id} ==={Colors.RESET}\n")
        print(f"📄 详情链接：https://github.com/{self.owner}/{self.repo}/actions/runs/{run_id}")
        print(f"🕐 监控间隔：{check_interval}秒")
        print(f"{'='*60}\n")
        
        self.start_time = time.time()
        check_count = 0
        max_checks = 360  # 最多监控 60 分钟
        
        while check_count < max_checks:
            check_count += 1
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            # 获取构建状态
            run = self.get_run_status(run_id)
            if not run:
                print(f"[{timestamp}] ❌ 无法获取状态")
                time.sleep(check_interval)
                continue
            
            status = run.get('status', 'unknown')
            conclusion = run.get('conclusion', '')
            
            # 状态变化时显示
            if status != self.last_status:
                duration = int(time.time() - self.start_time)
                minutes = duration // 60
                seconds = duration % 60
                
                status_emoji = {
                    'completed': '✅' if conclusion == 'success' else '❌',
                    'in_progress': '⏳',
                    'queued': '⏱️',
                    'requested': '📋'
                }.get(status, '⚪')
                
                print(f"[{timestamp}] {status_emoji} 状态：{status:12s} | 结论：{conclusion:10s} | 耗时：{minutes:02d}分{seconds:02d}秒")
                self.last_status = status
            
            # 检查是否完成
            if status == 'completed':
                self.notify_completion(run)
                return conclusion == 'success'
            
            time.sleep(check_interval)
        
        print(f"\n{Colors.RED}⏰ 监控超时 (60 分钟){Colors.RESET}")
        return False
    
    def notify_completion(self, run):
        """构建完成通知"""
        conclusion = run.get('conclusion')
        run_id = run.get('id')
        html_url = run.get('html_url')
        
        print(f"\n{'='*60}")
        
        if conclusion == 'success':
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 构建成功！{Colors.RESET}\n")
            print(f"📦 产物下载:")
            print(f"   https://github.com/{self.owner}/{self.repo}/actions/runs/{run_id}")
            print(f"   → 点击页面底部的 Artifacts 下载")
            print(f"\n📄 查看日志:")
            print(f"   {html_url}")
        elif conclusion == 'failure':
            print(f"{Colors.RED}{Colors.BOLD}❌ 构建失败！{Colors.RESET}\n")
            print(f"📄 查看错误日志:")
            print(f"   {html_url}")
            
            # 获取作业日志分析错误
            jobs = self.get_job_logs(run_id)
            failed_jobs = [j for j in jobs if j.get('conclusion') == 'failure']
            
            if failed_jobs:
                print(f"\n{Colors.BOLD}失败的作业:{Colors.RESET}")
                for job in failed_jobs:
                    job_name = job.get('name', 'unknown')
                    job_id = job.get('id')
                    print(f"   - {job_name} (ID: {job_id})")
                
                # 获取第一个失败作业的日志
                print(f"\n{Colors.BOLD}错误分析:{Colors.RESET}")
                for job in failed_jobs[:1]:  # 只分析第一个失败作业
                    logs = self.get_log_content(job.get('id'))
                    if logs:
                        # 提取错误信息
                        error_lines = [line for line in logs.split('\n') 
                                     if 'error' in line.lower() or 'Error' in line or 'failed' in line.lower()]
                        for line in error_lines[-10:]:  # 显示最后 10 条错误
                            if len(line) < 200:
                                print(f"   {Colors.RED}{line}{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}⚠️  构建{conclusion}{Colors.RESET}")
        
        print(f"{'='*60}\n")
    
    def run(self, run_id=None, check_interval=10):
        """运行监控"""
        print(f"{Colors.BOLD}{Colors.CYAN}")
        print("=" * 60)
        print("         🚀 GitHub Actions 构建监控")
        print("=" * 60)
        print(f"{Colors.RESET}")
        print(f"仓库：{self.owner}/{self.repo}")
        print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 如果没有指定 run_id，获取最近的运行中构建
        if not run_id:
            run = self.get_recent_run(status_filter='in_progress')
            if not run:
                run = self.get_recent_run(status_filter='queued')
            
            if not run:
                print(f"\n{Colors.YELLOW}⚠️  未找到正在运行的构建{Colors.RESET}")
                print(f"\n💡 触发新构建:")
                print(f"   python3 trigger-github-build.py --token YOUR_TOKEN")
                return False
            
            run_id = run.get('id')
            self.last_status = run.get('status')
        
        return self.monitor_run(run_id, check_interval)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="GitHub Actions 构建监控工具")
    parser.add_argument("--token", default=GITHUB_TOKEN, help="GitHub Token")
    parser.add_argument("--owner", default=GITHUB_OWNER, help="仓库所有者")
    parser.add_argument("--repo", default=GITHUB_REPO, help="仓库名称")
    parser.add_argument("--run-id", type=int, help="构建运行 ID")
    parser.add_argument("--interval", type=int, default=10, help="检查间隔（秒）")
    
    args = parser.parse_args()
    
    if args.token == "YOUR_GITHUB_TOKEN_HERE":
        print(f"{Colors.RED}❌ 请先配置 GitHub Token！{Colors.RESET}")
        print(f"\n使用方法:")
        print(f"  python3 monitor-github-build.py --token YOUR_TOKEN")
        sys.exit(1)
    
    monitor = GitHubMonitor(args.token, args.owner, args.repo)
    success = monitor.run(args.run_id, args.interval)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
