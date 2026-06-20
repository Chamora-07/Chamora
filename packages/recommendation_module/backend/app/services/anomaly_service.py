def detect_anomaly(metrics: dict) -> dict:
    cpu = metrics.get("cpu_percent", 0)
    memory = metrics.get("memory_percent", 0)

    flags = []

    if cpu > 80:
        flags.append({
            "type": "cpu",
            "value": cpu,
            "threshold": 80,
            "message": f"CPU usage is high at {cpu}%"
        })

    if memory > 75:
        flags.append({
            "type": "memory",
            "value": memory,
            "threshold": 75,
            "message": f"Memory usage is high at {memory}%"
        })

    if flags:
        return {
            "available": True,
            "status": "risk",
            "flags": flags
        }

    return {
        "available": True,
        "status": "safe",
        "flags": []
    }