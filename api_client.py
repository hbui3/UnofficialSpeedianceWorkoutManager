import time
import json
import requests
import os

class SpeedianceClient:
    def __init__(self):
        self.config_file = "config.json"
        self.credentials = self.load_config()
        self.region = self.credentials.get("region", "Global")
        self.base_url = "https://euapi.speediance.com" if self.region == "EU" else "https://api2.speediance.com"
        self.host = "euapi.speediance.com" if self.region == "EU" else "api2.speediance.com"
        self.library_cache = None 

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return {"user_id": "", "token": "", "region": "Global", "unit": 0}

    def save_config(self, user_id, token, region="Global", unit=0):
        self.credentials = {"user_id": user_id, "token": token, "region": region, "unit": unit}
        self.region = region
        self.host = "euapi.speediance.com" if self.region == "EU" else "api2.speediance.com"
        self.base_url = "https://" + self.host
        with open(self.config_file, 'w') as f:
            json.dump(self.credentials, f)

    def update_unit(self, unit):
        """Updates the unit setting on the server (0=Metric, 1=Imperial)"""
        url = f"{self.base_url}/api/app/userinfo"
        payload = {"unit": int(unit)}
        try:
            resp = requests.put(url, headers=self._get_headers(), json=payload)
            if resp.status_code == 200:
                # Update local config
                self.save_config(
                    self.credentials.get("user_id"), 
                    self.credentials.get("token"), 
                    self.credentials.get("region"),
                    unit
                )
                return True, "Unit updated successfully"
            else:
                return False, f"Failed to update unit: {resp.text}"
        except Exception as e:
            return False, str(e)

    def login(self, email, password):
        # Common headers for login requests
        headers = {
            "Host": self.host,
            "User-Agent": "Dart/3.9 (dart:io)",
            "Content-Type": "application/json",
            "Timestamp": str(int(time.time() * 1000)),
            "Utc_offset": "+0000",
            "Versioncode": "40304",
            "Mobiledevices": '{"brand":"google","device":"emulator64_x86_64_arm64","deviceType":"sdk_gphone64_x86_64","os":"","os_version":"31","manufacturer":"Google"}',
            "Timezone": "GMT",
            "Accept-Language": "en",
            "App_type": "SOFTWARE",
            "Connection": "keep-alive",
            "Accept-Encoding": "gzip, deflate, br"
        }

        # Step 1: Verify Identity
        verify_url = f"{self.base_url}/api/app/v2/login/verifyIdentity"
        verify_payload = {"type": 2, "userIdentity": email}
        
        try:
            resp = requests.post(verify_url, json=verify_payload, headers=headers)
            if resp.status_code != 200:
                return False, "Verify failed", f"Status: {resp.status_code}\nResponse: {resp.text}"
            
            verify_data = resp.json().get('data', {})
            if verify_data.get('isExist') is False:
                return False, "Account does not exist. Please register using the official Speediance mobile app first.", None
            
            if verify_data.get('hasPwd') is False:
                return False, "Account exists but has no password set. Please set a password in the Speediance mobile app.", None

            # Step 2: ByPass (Login with password)
            bypass_url = f"{self.base_url}/api/app/v2/login/byPass"
            bypass_payload = {"userIdentity": email, "password": password, "type": 2}
            
            resp = requests.post(bypass_url, json=bypass_payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                token = data.get('token')
                user_id = data.get('appUserId')
                
                if token and user_id:
                    self.save_config(str(user_id), token, self.region)
                    return True, "Login successful", None
                return False, "Token or appUserId not found in response", f"Response: {resp.text}"
            else:
                return False, "Login failed", f"Status: {resp.status_code}\nResponse: {resp.text}"
                
        except Exception as e:
            return False, "Connection Error", str(e)

    def logout(self):
        url = f"{self.base_url}/api/app/login/logout"
        headers = self._get_headers()
        headers["App_type"] = "SOFTWARE"
        headers["User-Agent"] = "Dart/3.9 (dart:io)"
        
        try:
            requests.post(url, headers=headers)
        except Exception as e:
            print(f"Logout error: {e}")
        
        self.save_config("", "")
        return True

    def _get_headers(self):
        return {
            "Host": self.host,
            "App_user_id": self.credentials.get("user_id", ""),
            "Token": self.credentials.get("token", ""),
            "Timestamp": str(int(time.time() * 1000)),
            "Versioncode": "40304",
            "Mobiledevices": '{"brand":"google","device":"emulator64_x86_64_arm64","deviceType":"sdk_gphone64_x86_64","os":"","os_version":"31","manufacturer":"Google"}',
            "Content-Type": "application/json",
            "User-Agent": "Dart/3.9 (dart:io)"
        }

    def get_library(self):
        if self.library_cache:
            return self.library_cache
            
        url = f"{self.base_url}/api/app/actionLibraryGroup/trainingPartGroup?tabId=1&deviceTypeList=1"
        try:
            resp = requests.get(url, headers=self._get_headers())
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                basic_list = []
                for muscle_group in data:
                    for action in muscle_group.get('actionLibraryGroupList', []):
                        basic_list.append(action)
                
                # Fetch details in batches to get full info (instructions, breathing, etc.)
                all_ids = [ex['id'] for ex in basic_list]
                detailed_library = []
                chunk_size = 50
                
                for i in range(0, len(all_ids), chunk_size):
                    chunk_ids = all_ids[i:i + chunk_size]
                    details = self.get_batch_details(chunk_ids)
                    detailed_library.extend(details)
                
                self.library_cache = detailed_library
                return detailed_library
        except Exception as e:
            print(f"Error fetching library: {e}")
        return []
    
    def get_accessories(self):
        url = f"{self.base_url}/api/app/accessories/list"
        try:
            resp = requests.get(url, headers=self._get_headers())
            return resp.json().get('data', [])
        except Exception as e:
            print(f"Error fetching accessories: {e}")
            return []
        
    def get_workout_detail(self, code):
        url = f"{self.base_url}/api/app/v3/customTrainingTemplate/detailByCode?code={code}"
        try:
            resp = requests.get(url, headers=self._get_headers())
            return resp.json().get('data', None)
        except Exception as e:
            print(f"Error fetching template detail: {e}")
            return None

    def get_user_workouts(self):
        url = f"{self.base_url}/api/app/v4/customTrainingTemplate/appPage?pageNo=1&pageSize=-1&deviceTypes=1"
        resp = requests.get(url, headers=self._get_headers())
        return resp.json().get('data', [])

    def delete_workout(self, template_id):
        url = f"{self.base_url}/api/app/customTrainingTemplate?ids={template_id}"
        requests.delete(url, headers=self._get_headers())

    def get_exercise_detail(self, exercise_id):
        url = f"{self.base_url}/api/app/actionLibraryGroup/{exercise_id}?isDisplay=1"
        resp = requests.get(url, headers=self._get_headers())
        return resp.json().get('data', {})

    def is_exercise_unilateral(self, group_id):
        detail = self.get_exercise_detail(group_id)
        return detail.get('isLeftRight') == 1

    def get_batch_details(self, group_ids):
        if not group_ids:
            return []
        query_parts = [f"ids={gid}" for gid in group_ids]
        query_str = "&".join(query_parts)
        url = f"{self.base_url}/api/app/actionLibraryGroup/list?{query_str}"
        
        try:
            resp = requests.get(url, headers=self._get_headers())
            return resp.json().get('data', [])
        except Exception as e:
            print(f"Error fetching batch details: {e}")
            return []

    def save_workout(self, name, exercises, template_id=None): 
        """
        Speichert (ohne ID) oder Aktualisiert (mit ID).
        Behebt den 'Parameter Error' durch saubere Trennung von weights und counterweight2.
        """
        
        group_ids = list(set([ex['groupId'] for ex in exercises]))
        details = self.get_batch_details(group_ids)
        
        id_map = {}
        for d in details:
            if d.get('actionLibraryList'):
                id_map[str(d['id'])] = d['actionLibraryList'][0]['id']
        
        action_library_list = []
        total_capacity = 0

        unilateral_check = {}
        for group_id in group_ids:
            unilateral_check[group_id] = self.is_exercise_unilateral(group_id)

        for ex in exercises:
            group_id = int(ex['groupId'])
            sets = ex['sets']
            preset_id = int(ex.get('preset_id', -1))
            
            is_unilateral = unilateral_check.get(group_id, False)

            user_variant_id = ex.get('variant_id')
            real_variant_id = int(user_variant_id) if user_variant_id and str(user_variant_id).isdigit() else id_map.get(str(ex['groupId']))
            
            if not real_variant_id:
                continue

            # Arrays für CSV (IMPORTANT: must be same length)
            reps_list = []
            weights_list = []  # only for custom
            counter_list = []  # only for preset
            break_list = []
            mode_list = []
            left_right_list = []
            level_list = []
            completion_list = []
            completion_method_list = []
            count_type_list = []
            
            set_capacity = 0

            for i, s in enumerate(sets):
                reps = int(s.get('reps', 0))
                weight_val = float(s.get('weight', 0))
                mode = int(s.get('mode', 1))
                rest = int(s.get('rest', 60))
                unit = str(s.get('unit', 'reps')).lower()

                # Unilateral Logic
                if is_unilateral:
                    left_right_list.append("1" if i % 2 == 0 else "2")
                else:
                    left_right_list.append("0")

                reps_list.append(str(reps))
                break_list.append(str(rest))
                mode_list.append(str(mode))
                level_list.append("0")

                # Completion fields: required by API (observed in app payloads)
                # - unit=='sec' => time-based completion
                # - unit=='reps' => rep-based completion
                if unit == 'sec':
                    completion_method_list.append("2")
                    count_type_list.append("2")
                else:
                    completion_method_list.append("1")
                    count_type_list.append("1")
                completion_list.append("1")

                # Weights vs counters
                if preset_id == -1:
                    api_weight = weight_val * 2.2
                    weights_list.append(f"{api_weight:.1f}")
                    set_capacity += (reps * api_weight)
                else:
                    # For presets, we MUST populate weights_list with dummy values (e.g. 3.5)
                    # AND populate counter_list with the RM value.
                    # The API seems to drop counterweight2 if weights is empty or missing?
                    # Or maybe it's just that we need to send weights even if unused.
                    weights_list.append("3.5") 
                    counter_list.append(str(int(weight_val)))
                    set_capacity += (reps * weight_val * 2.2)

            total_capacity += set_capacity

            final_weights = ",".join(weights_list)
            final_counter = ",".join(counter_list) if preset_id != -1 else ""

            action_obj = {
                # Required identifiers
                "groupId": group_id,
                "actionLibraryId": int(real_variant_id),

                "templatePresetId": preset_id,

                # Per-set CSV
                "setsAndReps": ",".join(reps_list),

                # Some backends expect both fields present
                "breakTime": ",".join(break_list),
                "breakTime2": ",".join(break_list),

                "sportMode": ",".join(mode_list),
                "leftRight": ",".join(left_right_list),

                # Completion-related
                "selectCompletionMethod": ",".join(completion_list),
                "completionMethod": ",".join(completion_method_list),
                "countType": ",".join(count_type_list),

                # Weights
                "weights": final_weights,
                "counterweight2": final_counter,
                "counterweight": final_counter, # Try sending both counterweight and counterweight2

                "level": ",".join(level_list),
                "capacity": set_capacity,
            }
            action_library_list.append(action_obj)

        payload = {
            "name": name,
            "actionLibraryList": action_library_list,
            "totalCapacity": total_capacity,
            "deviceType": 1,
            "bgColor": 0
        }

        if template_id:
            payload['id'] = int(template_id)

        url = f"{self.base_url}/api/app/v2/customTrainingTemplate"
        resp = requests.post(url, headers=self._get_headers(), json=payload)
        return resp.json()