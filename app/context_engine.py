import math

class ContextAnalyzer:
    def __init__(self):
        self.user_baselines = {}

    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculates distance in meters between two GPS coordinates."""
        R = 6371000  # Radius of Earth in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2.0) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * \
            math.sin(delta_lambda / 2.0) ** 2
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        return distance

    def evaluate_live_context(self, username: str, live_data: dict):
        """
        Evaluates real-time IP, 500m Geo-Fence, and Bluetooth decay.
        """
        # 1. Establish Baseline on first check
        if username not in self.user_baselines:
            self.user_baselines[username] = {
                "trusted_ips": [live_data.get("ip")], # Can store multiple trusted IPs
                "baseline_lat": float(live_data.get("lat", 0)),
                "baseline_lon": float(live_data.get("lon", 0)),
                "bt_miss_count": 0
            }
            return {"IP": 0.05, "GEO": 0.05, "BT": 0.05, "CP_TOTAL": 0.05, "misses": 0, "distance_m": 0}

        baseline = self.user_baselines[username]
        
        # 2. IP Risk (Must be in trusted list)
        ip_risk = 0.05 if live_data.get("ip") in baseline["trusted_ips"] else 0.85
        
        # 3. Geo-Fence Risk (The 500-meter rule)
        current_lat = float(live_data.get("lat", 0))
        current_lon = float(live_data.get("lon", 0))
        
        distance_meters = self._haversine_distance(
            baseline["baseline_lat"], baseline["baseline_lon"], 
            current_lat, current_lon
        )
        
        # If they moved more than 500m, risk spikes to 0.95!
        geo_risk = 0.05 if distance_meters <= 500 else 0.95
        
        # 4. Bluetooth Decay
        is_nearby = live_data.get("bluetooth_nearby", True)
        if is_nearby:
            baseline["bt_miss_count"] = 0
            bt_risk = 0.05
        else:
            baseline["bt_miss_count"] += 1
            misses = baseline["bt_miss_count"]
            if misses == 1: bt_risk = 0.35
            elif misses == 2: bt_risk = 0.65
            else: bt_risk = 0.95

        # 5. Calculate total CP
        cp_total = (ip_risk * 0.33) + (geo_risk * 0.33) + (bt_risk * 0.34)

        return {
            "IP": round(ip_risk, 3),
            "GEO": round(geo_risk, 3),
            "BT": round(bt_risk, 3),
            "CP_TOTAL": round(cp_total, 3),
            "misses": baseline["bt_miss_count"],
            "distance_m": round(distance_meters, 1)
        }