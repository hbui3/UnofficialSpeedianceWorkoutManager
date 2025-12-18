from api_client import SpeedianceClient
import json
from datetime import datetime

client = SpeedianceClient()
# Use current month or a known month
current_month = datetime.now().strftime("%Y-%m")
print(f"Fetching calendar for {current_month}...")

try:
    data = client.get_calendar_month(current_month)
    # Find a day with training plans
    found = False
    for day in data:
        if day.get('trainingPlanList'):
            print(json.dumps(day['trainingPlanList'], indent=2))
            found = True
            break
    
    if not found:
        print("No training plans found in this month.")
        # Try previous month just in case
        prev_month = "2025-11" # Assuming current is Dec 2025 based on context
        print(f"Trying {prev_month}...")
        data = client.get_calendar_month(prev_month)
        for day in data:
            if day.get('trainingPlanList'):
                print(json.dumps(day['trainingPlanList'], indent=2))
                found = True
                break

except Exception as e:
    print(f"Error: {e}")
