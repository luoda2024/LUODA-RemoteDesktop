#!/usr/bin/env python3
"""
LUODA CI 构建日志实时监控工具

使用方法:
    python3 ci-logger.py [pipeline_id]

需要设置环境变量:
    export GITEE_TOKEN=your_token_here
"""

import requests
import time
import os
import sys
from datetime import datetime

class GiteeCILogger:
    def __init__(self, owner="soulemo_1", repo="dicad"):
        self.owner = owner
        self.repo = repo
        self.base_url = "https://gitee.com/api/v5"
        self.token = os.environ.get('GITEE_TOKEN', '')
        
        if not self.token:
            print("❌ 错误：请设置 GITEE_TOKEN 环境变量")
            print("获取方式：https://gitee.com/profile/personal_access_tokens")
            sys.exit(1)
        
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.pipeline_id = None
        self.job_ids = []
        self.last_log_positions = {}
        
    def get_latest_pipeline(self):
        """获取最新的流水线"""
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pipelines"
        params = {"page": 1, "per_page": 1}
        
        response = requests.get(url, headers=self.headers, params=params)
        if response.status_code == 200:
            pipelines = response.json()
            if pipelines:
                self.pipeline_id = pipelines[0]['id']
                return self.pipeline_id
        return None
    
    def get_pipeline_status(self, pipeline_id=None):
        """获取流水线状态"""
        if not pipeline_id:
            pipeline_id = self.pipeline_id
            
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pipelines/{pipeline_id}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        return None
    
    def get_pipeline_jobs(self, pipeline_id=None):
        """获取流水线的所有任务"""
        if not pipeline_id:
            pipeline_id = self.pipeline_id
            
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pipelines/{pipeline_id}/jobs"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            jobs = response.json()
            self.job_ids = [job['id'] for job in jobs]
            return jobs
        return []
    
    def get_job_log(self, job_id):
        """获取任务日志"""
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pipelines/{self.pipeline_id}/jobs/{job_id}/log"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.text
        return ""
    
    def trigger_pipeline(self, pipeline_name="luoda-full-build", ref="master"):
        """触发新的流水线"""
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/pipelines"
        data = {
            "ref": ref,
            "pipeline_name": pipeline_name,
            "trigger_type": "manual"
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code == 201:
            pipeline = response.json()
            self.pipeline_id = pipeline['id']
            print(f"✅ 构建已触发! 流水线 ID: {self.pipeline_id}")
            return self.pipeline_id
        else:
            print(f"❌ 触发失败：{response.status_code}")
            print(response.text)
            return None
    
    def monitor(self, pipeline_id=None, interval=5, timeout=3600):
        """监控流水线"""
        if not pipeline_id:
            self.get_latest_pipeline()
        else:
            self.pipeline_id = pipeline_id
            
        if not self.pipeline_id:
            print("❌ 未找到流水线")
            return False
        
        print(f"⏳ 开始监控流水线 {self.pipeline_id} ...")
        print(f"📄 详情：https://gitee.com/soulemo_1/dicad/pipelines/{self.pipeline_id}")
        print("=" * 60)
        
        start_time = time.time()
        jobs_initialized = False
        
        while time.time() - start_time < timeout:
            # 获取流水线状态
            status = self.get_pipeline_status()
            if not status:
                print("❌ 无法获取流水线状态")
                time.sleep(interval)
                continue
            
            state = status.get('state', 'unknown')
            trigger = status.get('trigger', 'manual')
            updated_at = status.get('updated_at', '')
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] 状态：{state:10s} | 触发：{trigger}")
            
            # 获取并显示任务详情
            if not jobs_initialized and state in ['running', 'pending']:
                jobs = self.get_pipeline_jobs()
                if jobs:
                    print(f"📋 任务列表:")
                    for job in jobs:
                        job_name = job.get('name', 'unknown')
                        job_state = job.get('state', 'unknown')
                        print(f"   - {job_name}: {job_state}")
                    jobs_initialized = True
                    print("-" * 60)
            
            # 实时日志（仅当有运行的任务时）
            if state == 'running' and self.job_ids:
                jobs = self.get_pipeline_jobs()
                for job in jobs:
                    if job.get('state') == 'running':
                        log = self.get_job_log(job['id'])
                        if log:
                            lines = log.split('\n')
                            # 显示最后 5 行
                            for line in lines[-5:]:
                                if line.strip():
                                    print(f"   | {line}")
            
            # 检查是否完成
            if state in ['success', 'failure', 'cancelled', 'timeout']:
                print("=" * 60)
                if state == 'success':
                    print(f"✅ 构建成功!")
                    print(f"📦 产物：https://gitee.com/soulemo_1/dicad/pipelines/{self.pipeline_id}/artifacts")
                    return True
                elif state == 'failure':
                    print(f"❌ 构建失败!")
                    print(f"📄 日志：https://gitee.com/soulemo_1/dicad/pipelines/{self.pipeline_id}/jobs")
                    return False
                else:
                    print(f"⚠️  构建{state}")
                    return False
            
            time.sleep(interval)
        
        print(f"⏰ 监控超时 ({timeout}秒)")
        return None


def main():
    print("=" * 60)
    print("  LUODA CI 构建日志监控")
    print("=" * 60)
    print()
    
    logger = GiteeCILogger()
    
    # 命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == 'trigger':
            # 触发新构建
            pipeline_id = logger.trigger_pipeline()
            if pipeline_id:
                logger.monitor()
        elif sys.argv[1].isdigit():
            # 监控指定 ID 的构建
            logger.monitor(pipeline_id=int(sys.argv[1]))
        else:
            print("使用方法:")
            print("  python3 ci-logger.py           # 监控最新构建")
            print("  python3 ci-logger.py trigger   # 触发并监控新构建")
            print("  python3 ci-logger.py <ID>      # 监控指定 ID 的构建")
    else:
        # 默认监控最新构建
        logger.get_latest_pipeline()
        if logger.pipeline_id:
            logger.monitor()
        else:
            print("未找到正在运行的构建")
            print()
            print("使用方法:")
            print("  python3 ci-logger.py trigger   # 触发并监控新构建")


if __name__ == "__main__":
    main()
