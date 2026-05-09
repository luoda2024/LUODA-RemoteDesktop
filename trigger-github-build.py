#!/usr/bin/env python3
"""
GitHub Actions 构建触发工具
使用方法：python3 trigger-github-build.py

功能:
1. 触发 GitHub Actions 构建
2. 支持指定构建类型（all/windows/android/linux）
3. 自动获取构建状态
"""

import requests
import json
import sys
import os

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

class GitHubTrigger:
    def __init__(self, token, owner=GITHUB_OWNER, repo=GITHUB_REPO):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = f"https://api.github.com/repos/{owner}/{repo}"
    
    def get_workflow_id(self, workflow_name="build.yml"):
        """获取工作流 ID"""
        url = f"{self.base_url}/actions/workflows"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            print(f"{Colors.RED}❌ 获取工作流失败：{response.json().get('message')}{Colors.RESET}")
            return None
        
        workflows = response.json().get('workflows', [])
        for wf in workflows:
            if wf.get('name') == workflow_name or wf.get('path') == f".github/workflows/{workflow_name}":
                return wf.get('id')
        
        print(f"{Colors.YELLOW}⚠️  未找到工作流：{workflow_name}{Colors.RESET}")
        return None
    
    def trigger_workflow(self, workflow_id, ref="master", build_type="all"):
        """触发工作流"""
        url = f"{self.base_url}/actions/workflows/{workflow_id}/dispatches"
        
        data = {
            "ref": ref,
            "inputs": {
                "build_type": build_type
            }
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code == 204:
            print(f"{Colors.GREEN}✅ 构建已触发！{Colors.RESET}")
            print(f"   仓库：{self.owner}/{self.repo}")
            print(f"   分支：{ref}")
            print(f"   类型：{build_type}")
            print(f"\n📄 查看构建：https://github.com/{self.owner}/{self.repo}/actions")
            return True
        else:
            error = response.json().get('message', 'Unknown error')
            print(f"{Colors.RED}❌ 触发失败：{error}{Colors.RESET}")
            return False
    
    def get_recent_runs(self, limit=5):
        """获取最近的构建运行"""
        url = f"{self.base_url}/actions/runs"
        params = {"per_page": limit}
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code != 200:
            return []
        
        return response.json().get('workflow_runs', [])
    
    def display_runs(self, runs):
        """显示构建运行列表"""
        print(f"\n{Colors.BOLD}=== 📊 最近构建 ==={Colors.RESET}\n")
        
        for i, run in enumerate(runs, 1):
            status = run.get('status', 'unknown')
            conclusion = run.get('conclusion', '')
            event = run.get('event', 'push')
            created = run.get('created_at', '')[:19].replace('T', ' ')
            run_id = run.get('id')
            workflow_name = run.get('name', 'workflow')
            
            # 状态图标
            if status == 'completed':
                if conclusion == 'success':
                    icon = f"{Colors.GREEN}✅{Colors.RESET}"
                elif conclusion == 'failure':
                    icon = f"{Colors.RED}❌{Colors.RESET}"
                else:
                    icon = f"{Colors.YELLOW}⚠️{Colors.RESET}"
            elif status == 'in_progress':
                icon = f"{Colors.BLUE}⏳{Colors.RESET}"
            elif status == 'queued':
                icon = f"{Colors.CYAN}⏱️{Colors.RESET}"
            else:
                icon = "⚪"
            
            print(f"{icon} #{i} ID: {run_id} | {workflow_name}")
            print(f"    状态：{status:12s} | 结论：{conclusion:10s} | 事件：{event:8s}")
            print(f"    时间：{created}")
            print(f"    链接：https://github.com/{self.owner}/{self.repo}/actions/runs/{run_id}")
            print()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="GitHub Actions 构建触发工具")
    parser.add_argument("--token", default=GITHUB_TOKEN, help="GitHub Token")
    parser.add_argument("--owner", default=GITHUB_OWNER, help="仓库所有者")
    parser.add_argument("--repo", default=GITHUB_REPO, help="仓库名称")
    parser.add_argument("--ref", default="master", help="分支或标签")
    parser.add_argument("--type", default="all", choices=["all", "windows", "android", "linux"],
                       help="构建类型")
    parser.add_argument("--list", action="store_true", help="列出最近的构建")
    parser.add_argument("--workflow", default="build.yml", help="工作流文件名")
    
    args = parser.parse_args()
    
    if args.token == "YOUR_GITHUB_TOKEN_HERE":
        print(f"{Colors.RED}❌ 请先配置 GitHub Token！{Colors.RESET}")
        print(f"\n使用方法:")
        print(f"  1. 访问：https://github.com/settings/tokens/new")
        print(f"  2. 勾选权限：repo, workflow")
        print(f"  3. 生成 Token")
        print(f"  4. 运行：python3 trigger-github-build.py --token YOUR_TOKEN")
        sys.exit(1)
    
    trigger = GitHubTrigger(args.token, args.owner, args.repo)
    
    if args.list:
        runs = trigger.get_recent_runs()
        if runs:
            trigger.display_runs(runs)
        else:
            print(f"{Colors.YELLOW}⚠️  未找到构建记录{Colors.RESET}")
        return
    
    # 触发构建
    workflow_id = trigger.get_workflow_id(args.workflow)
    if workflow_id:
        success = trigger.trigger_workflow(workflow_id, args.ref, args.type)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
