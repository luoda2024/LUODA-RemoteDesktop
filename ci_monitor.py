#!/usr/bin/env python3
"""
LUODA CI/CD Smart Monitor - checks build status and detects issues.
Called by auto-monitor.yml workflow every 30 minutes.
"""
import os, sys, json, urllib.request, time, re, subprocess
from datetime import datetime, timezone, timedelta

GITHUB_REPO = "luoda2023/LUODA-RemoteDesktop"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
API_BASE = "https://api.github.com"

def api_request(endpoint):
    """Make authenticated GitHub API request."""
    url = f"{API_BASE}{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {GITHUB_TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "LUODA-CI-Monitor")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"⚠️  API request failed: {e}")
        return None

def check_recent_runs():
    """Check the most recent workflow runs for issues."""
    runs = api_request(f"/repos/{GITHUB_REPO}/actions/runs?per_page=10")
    if not runs:
        return {"status": "error", "message": "Cannot fetch workflow runs"}
    
    failures = []
    in_progress = []
    
    for run in runs.get("workflow_runs", []):
        name = run.get("name", "?")
        status = run.get("status", "?")
        conclusion = run.get("conclusion", "?")
        created = run.get("created_at", "?")
        run_id = run.get("id")
        
        if conclusion == "failure":
            failures.append({"name": name, "id": run_id, "created": created})
            print(f"❌ FAILURE: [{run_id}] {name} at {created}")
        elif status == "in_progress":
            created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            elapsed = datetime.now(timezone.utc) - created_dt
            in_progress.append({"name": name, "id": run_id, "elapsed": str(elapsed)})
            print(f"🔄 IN PROGRESS: [{run_id}] {name} (elapsed: {elapsed})")
            # Check for stuck builds (>2 hours)
            if elapsed.total_seconds() > 7200:
                print(f"⚠️  STUCK BUILD: {name} has been running for {elapsed}")
    
    result = {"status": "ok", "failures": failures, "in_progress": in_progress}
    
    if failures:
        result["status"] = "failure"
    elif in_progress:
        result["status"] = "in_progress"
    
    return result


def check_build_artifacts():
    """Check if build artifacts exist and have reasonable sizes."""
    # Get the latest completed build run
    runs = api_request(f"/repos/{GITHUB_REPO}/actions/runs?per_page=20&status=completed&conclusion=success")
    if not runs:
        return {"status": "no_runs"}
    
    artifacts_found = {}
    for run in runs.get("workflow_runs", []):
        if run.get("name") != "LUODA Build All Platforms":
            continue
        run_id = run.get("id")
        artifacts = api_request(f"/repos/{GITHUB_REPO}/actions/runs/{run_id}/artifacts")
        if artifacts:
            for art in artifacts.get("artifacts", []):
                name = art.get("name", "?")
                size = art.get("size_in_bytes", 0)
                expired = art.get("expired", False)
                if not expired:
                    artifacts_found[name] = size
                    size_mb = size / (1024*1024)
                    status = "✅" if size > 5*1024*1024 else "⚠️"
                    print(f"  {status} {name}: {size_mb:.1f} MB")
            break  # Only check the latest successful build
    
    if not artifacts_found:
        return {"status": "no_artifacts", "message": "No build artifacts found"}
    
    # Check for expected artifacts
    expected = {
        "LUODA-windows-exe": 20*1024*1024,  # ~20MB
        "LUODA-android-apk": 20*1024*1024,  # ~20MB
        "LUODA-linux-deb": 20*1024*1024,    # ~20MB
    }
    
    issues = []
    for name, min_size in expected.items():
        found = False
        for art_name, size in artifacts_found.items():
            if name in art_name or name.lower() in art_name.lower():
                found = True
                if size < min_size * 0.5:
                    issues.append(f"Artifact {art_name} is too small: {size/(1024*1024):.1f} MB (expected ~{min_size/(1024*1024):.0f} MB)")
                break
        if not found:
            issues.append(f"Missing artifact: {name}")
    
    if issues:
        return {"status": "artifact_issues", "issues": issues}
    
    return {"status": "ok", "artifacts": artifacts_found}


def main():
    print("=" * 60)
    print(f"🚀 LUODA CI/CD Monitor — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Check recent workflow runs
    print("\n📊 Checking recent workflow runs...")
    runs_status = check_recent_runs()
    
    # Check artifacts
    print("\n📦 Checking build artifacts...")
    artifacts_status = check_build_artifacts()
    
    # Summary
    print("\n📋 Summary:")
    has_issues = False
    
    if runs_status.get("status") == "failure":
        print(f"  ❌ {len(runs_status.get('failures', []))} failed workflow run(s)")
        has_issues = True
    elif runs_status.get("status") == "in_progress":
        print(f"  🔄 {len(runs_status.get('in_progress', []))} workflow run(s) in progress")
    else:
        print("  ✅ All recent workflow runs passed")
    
    if artifacts_status.get("status") == "artifact_issues":
        for issue in artifacts_status.get("issues", []):
            print(f"  ⚠️  {issue}")
        has_issues = True
    elif artifacts_status.get("status") == "no_artifacts":
        print("  ⚠️  No build artifacts found")
        has_issues = True
    elif artifacts_status.get("status") == "ok":
        print("  ✅ Build artifacts look good")
    
    if has_issues:
        print("\n⚠️  Issues detected — writing expert report for auto_fix.py")
        with open("expert_report_monitor.txt", "w") as f:
            f.write("# LUODA CI/CD Issues Report\n\n")
            for f_info in runs_status.get("failures", []):
                f.write(f"## Failed: {f_info['name']} (Run {f_info['id']})\n")
                f.write(f"  Created: {f_info['created']}\n\n")
            for issue in artifacts_status.get("issues", []):
                f.write(f"## Artifact Issue: {issue}\n\n")
        return 1
    else:
        print("\n✅ All systems normal")
        return 0


if __name__ == "__main__":
    sys.exit(main())
