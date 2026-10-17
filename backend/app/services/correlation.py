from typing import List
from app.models.alarm import Alarm

def correlate_alarms(alarms: List[Alarm]) -> List[Alarm]:
    """
    सरल इवेंट कोरिलेशन: एक ही डिवाइस के कई अलार्म्स में से केवल सबसे गंभीर अलार्म को रखें।
    """
    correlated = {}
    for alarm in alarms:
        # यदि उस डिवाइस के लिए पहले से कोई अलार्म है, तो केवल अधिक गंभीर को रखें
        if alarm.device_id not in correlated or alarm.severity == "critical":
            correlated[alarm.device_id] = alarm
    return list(correlated.values())