# app/utils/system_utils.py
import psutil

def get_cpu_usage() -> float:
    return psutil.cpu_percent(interval=0.5)

def get_memory_usage() -> dict:
    mem = psutil.virtual_memory()
    return {
        "total": mem.total,
        "available": mem.available,
        "percent": mem.percent,
        "used": mem.used
    }

def get_disk_usage(path: str = "/") -> dict:
    try:
        disk = psutil.disk_usage(path)
        return {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        }
    except Exception:
        return {"total": 0, "used": 0, "free": 0, "percent": 0.0}

def get_top_processes(limit: int = 10) -> list:
    procs = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = proc.info
            if info['name']:
                procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # Sort processes heavily taxing the CPU layer
    procs = sorted(procs, key=lambda p: p['cpu_percent'] or 0.0, reverse=True)
    return procs[:limit]