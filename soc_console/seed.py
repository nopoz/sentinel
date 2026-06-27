SCENARIOS = {
    "alerts": [
        {"id": "1407", "title": "Suspicious PowerShell on WIN-4521",
         "severity": "high", "asset_id": "WIN-4521",
         "evidence": ["Encoded PowerShell spawned from winword.exe",
                      "Outbound beacon to 185.220.101.45 every 60s",
                      "Credential access attempt on lsass.exe"],
         "recommended": "quarantine"},
        {"id": "1408", "title": "Single failed login from new geo",
         "severity": "low", "asset_id": "WIN-9001",
         "evidence": ["One failed RDP login from a new country",
                      "No follow-on activity observed"],
         "recommended": "escalate"},
    ],
    "assets": {
        "WIN-4521": {"id": "WIN-4521", "hostname": "WIN-4521", "ip": "10.0.4.21", "status": "active"},
        "WIN-9001": {"id": "WIN-9001", "hostname": "WIN-9001", "ip": "10.0.9.1", "status": "active"},
    },
}
