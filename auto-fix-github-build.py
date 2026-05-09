#!/usr/bin/env python3
"""
GitHub Actions 构建错误自动修复工具
使用方法：python3 auto-fix-github-build.py --token YOUR_TOKEN

功能:
1. 获取失败的构建日志
2. 分析错误原因
3. 提供修复建议
4. 自动提交修复（可选）
"""

import requests
import re
import sys
import os
from datetime import datetime

# 配置
GITHUB_OWNER = "luoda2023"
GITHUB_REPO = "LUODA-RemoteDesktop"
GITHUB_TOKEN = "YOUR_GITHUB_TOKEN_HERE"

class Colors:
    RESET = "\033[0m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"

class ErrorFixer:
    def __init__(self, token, owner=GITHUB_OWNER, repo=GITHUB_REPO):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = f"https://api.github.com/repos/{owner}/{repo}"
    
    def get_failed_run(self):
        """获取最近的失败构建"""
        url = f"{self.base_url}/actions/runs"
        params = {"per_page": 10}
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code != 200:
            return None
        
        runs = response.json().get('workflow_runs', [])
        for run in runs:
            if run.get('status') == 'completed' and run.get('conclusion') == 'failure':
                return run
        return None
    
    def get_failed_jobs(self, run_id):
        """获取失败的作业"""
        url = f"{self.base_url}/actions/runs/{run_id}/jobs"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            return []
        
        jobs = response.json().get('jobs', [])
        return [j for j in jobs if j.get('conclusion') == 'failure']
    
    def get_job_logs(self, job_id):
        """获取作业日志"""
        url = f"{self.base_url}/actions/jobs/{job_id}/logs"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.text
        return ""
    
    def analyze_error(self, logs):
        """分析错误日志"""
        errors = []
        
        # Rust 编译错误
        if 'error[E' in logs:
            match = re.search(r'error\[E\d+\]: (.+?)(?:\n-->|\n\n)', logs, re.DOTALL)
            if match:
                errors.append({
                    'type': 'rust_compile',
                    'message': match.group(1).strip(),
                    'suggestion': self._suggest_rust_fix(match.group(0))
                })
        
        # 依赖错误
        if 'failed to select a version' in logs.lower():
            errors.append({
                'type': 'dependency',
                'message': '依赖版本冲突',
                'suggestion': '检查 Cargo.toml 中的依赖版本，或运行 cargo update'
            })
        
        # Flutter 错误
        if 'flutter' in logs.lower() and ('error' in logs.lower() or 'failed' in logs.lower()):
            if 'pub get' in logs.lower():
                errors.append({
                    'type': 'flutter_pub',
                    'message': 'Flutter 依赖获取失败',
                    'suggestion': '检查 flutter/pubspec.yaml 格式，或运行 flutter clean'
                })
            elif 'build apk' in logs.lower():
                errors.append({
                    'type': 'flutter_build',
                    'message': 'Flutter 构建失败',
                    'suggestion': '检查 Android SDK 配置或 Java 版本'
                })
        
        # 内存不足
        if 'out of memory' in logs.lower() or 'killed' in logs.lower():
            errors.append({
                'type': 'memory',
                'message': '内存不足',
                'suggestion': '尝试在更大的 runner 上构建，或减少并行度'
            })
        
        # 网络错误
        if 'network' in logs.lower() and 'error' in logs.lower():
            errors.append({
                'type': 'network',
                'message': '网络错误',
                'suggestion': '检查网络连接，或添加重试机制'
            })
        
        # 未找到错误
        if not errors:
            # 提取最后几条错误日志
            error_lines = [line for line in logs.split('\n') 
                         if 'error' in line.lower() or 'Error' in line or 'failed' in line.lower()]
            if error_lines:
                errors.append({
                    'type': 'unknown',
                    'message': error_lines[-1][:200] if error_lines else '未知错误',
                    'suggestion': '请检查完整日志'
                })
        
        return errors
    
    def _suggest_rust_fix(self, error_detail):
        """提供 Rust 错误修复建议"""
        suggestions = {
            'E0432': '添加缺少的 import 语句',
            'E0425': '检查变量名或添加 missing 声明',
            'E0308': '检查类型是否匹配',
            'E0599': '检查方法是否存在于该类型',
            'E0433': '检查模块路径是否正确',
        }
        
        for code, suggestion in suggestions.items():
            if code in error_detail:
                return f"Rust 错误 {code}: {suggestion}"
        
        return "Rust 编译错误，请检查代码语法"
    
    def create_fix_commit(self, error_type, fix_description):
        """创建修复提交（需要额外权限）"""
        print(f"\n{Colors.YELLOW}⚠️  自动修复功能需要额外配置{Colors.RESET}")
        print("建议手动修复步骤:")
        print(f"  1. 根据错误分析修改代码")
        print(f"  2. git add . && git commit -m 'fix: {fix_description}'")
        print(f"  3. git push origin master")
    
    def run(self):
        """运行错误分析"""
        print(f"{Colors.BOLD}{Colors.CYAN}")
        print("=" * 60)
        print("         🔧 GitHub Actions 错误分析修复")
        print("=" * 60)
        print(f"{Colors.RESET}")
        
        # 获取失败的构建
        run = self.get_failed_run()
        if not run:
            print(f"{Colors.GREEN}✅ 未找到失败的构建{Colors.RESET}")
            return True
        
        run_id = run.get('id')
        html_url = run.get('html_url')
        
        print(f"发现失败的构建：{run_id}")
        print(f"链接：{html_url}\n")
        
        # 获取失败的作业
        failed_jobs = self.get_failed_jobs(run_id)
        if not failed_jobs:
            print(f"{Colors.YELLOW}⚠️  未找到失败的作业{Colors.RESET}")
            return False
        
        print(f"失败的作业数量：{len(failed_jobs)}\n")
        
        # 分析每个失败作业
        all_errors = []
        for job in failed_jobs:
            job_name = job.get('name', 'unknown')
            job_id = job.get('id')
            
            print(f"{Colors.BOLD}分析作业：{job_name}{Colors.RESET}")
            
            logs = self.get_job_logs(job_id)
            errors = self.analyze_error(logs)
            
            for error in errors:
                print(f"  类型：{error['type']}")
                print(f"  错误：{error['message']}")
                print(f"  建议：{error['suggestion']}")
                print()
            
            all_errors.extend(errors)
        
        # 总结
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}📋 修复建议总结:{Colors.RESET}")
        for i, error in enumerate(all_errors, 1):
            print(f"  {i}. [{error['type']}] {error['suggestion']}")
        
        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="GitHub Actions 错误分析修复工具")
    parser.add_argument("--token", default=GITHUB_TOKEN, help="GitHub Token")
    parser.add_argument("--owner", default=GITHUB_OWNER, help="仓库所有者")
    parser.add_argument("--repo", default=GITHUB_REPO, help="仓库名称")
    
    args = parser.parse_args()
    
    if args.token == "YOUR_GITHUB_TOKEN_HERE":
        print(f"{Colors.RED}❌ 请先配置 GitHub Token！{Colors.RESET}")
        print(f"\n使用方法:")
        print(f"  python3 auto-fix-github-build.py --token YOUR_TOKEN")
        sys.exit(1)
    
    fixer = ErrorFixer(args.token, args.owner, args.repo)
    success = fixer.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
