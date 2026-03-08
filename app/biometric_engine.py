import os
import pickle
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

# The 12 exact features required by the model
MODEL_FEATURES = [
    'Dwell_Mean', 'Dwell_Min', 'Dwell_Max', 
    'Flight_Mean', 'Flight_Min', 'Flight_Max', 
    'DD_Mean', 'DD_Min', 'DD_Max', 
    'UU_Mean', 'UU_Min', 'UU_Max'
]

class BiometricBrain:
    def __init__(self, model_storage_path='user_models'):
        self.storage_path = model_storage_path
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)

    def _get_model_path(self, user_id):
        # Sanitize username to be a safe filename
        safe_id = "".join([c for c in user_id if c.isalnum()])
        return os.path.join(self.storage_path, f"user_{safe_id}.pkl")

    def train_new_user(self, user_id, raw_vectors):
        """
        TRAINING PHASE (Calibration)
        """
        try:
            # 1. Convert to Numpy Array
            real_data = np.array(raw_vectors) 
            
            # 2. Data Augmentation (The "50 Session" Hack)
            mean_vector = np.mean(real_data, axis=0)
            
            # --- THE FIX: Force a minimum variance of 15.0 so the cloud is wide and visible ---
            std_vector = np.std(real_data, axis=0)
            std_vector = np.maximum(std_vector, 15.0) 

            synthetic_data = []
            
            # Generate 50 synthetic points
            for _ in range(50):
                # We use 1.0 here instead of 0.8 to give the cloud a realistic, natural spread
                noise = np.random.normal(0, std_vector * 1.0) 
                synthetic_point = mean_vector + noise
                synthetic_data.append(synthetic_point)

            # Combine Real + Synthetic
            X = np.vstack([real_data, synthetic_data])
            
            # 3. Build Model (PCA)
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            pca = PCA(n_components=2)
            X_pca = pca.fit_transform(X_scaled)

            centroid = np.mean(X_pca, axis=0)
            dists = np.linalg.norm(X_pca - centroid, axis=1)
            
            # Set threshold at 2 Standard Deviations for stricter security
            threshold = float(dists.mean() + (2 * dists.std()))

            model_data = {
                'scaler': scaler,
                'pca': pca,
                'centroid': centroid,
                'threshold': threshold,
                # This saves the 53 wide points into the file
                'training_cloud_2d': X_pca.tolist() 
            }

            with open(self._get_model_path(user_id), 'wb') as f:
                pickle.dump(model_data, f)
            
            return {"success": True, "threshold": threshold, "msg": "Trained on 50 synthetic sessions"}

        except Exception as e:
            print(f"Train Error: {e}")
            return {"success": False, "error": str(e)}

    def verify_live_data(self, user_id, live_vector):
        """
        VERIFICATION PHASE (Live Check)
        Input: List of 12 floats
        """
        model_path = self._get_model_path(user_id)
        
        # If user has no model, return "Unverified" (or High Risk)
        if not os.path.exists(model_path):
            return {"status": "Unregistered", "risk": 0}

        try:
            with open(model_path, 'rb') as f:
                model = pickle.load(f)

            # Convert list to array and reshape for single sample
            vector = np.array(live_vector).reshape(1, -1)
            
            # Transform using the saved scaler and PCA
            scaled = model['scaler'].transform(vector)
            pca_point = model['pca'].transform(scaled)
            
            # Calculate distance from centroid
            distance = float(np.linalg.norm(pca_point - model['centroid']))
            threshold = model['threshold']
            
            # Anomaly Logic
            is_anomaly = distance > threshold
            
            # Risk Calculation (0-100)
            # Normal range is 0 to threshold. If distance > threshold, risk spikes.
            if threshold > 0:
                risk_score = (distance / threshold) * 50
            else:
                risk_score = 0
                
            if is_anomaly:
                # If it's an anomaly, risk starts at 75% and goes up
                risk_score = max(75, min(100, risk_score))
            else:
                # If verified, risk is capped at 50%
                risk_score = min(50, risk_score)

            return {
                "status": "Anomaly" if is_anomaly else "Verified",
                "distance": round(distance, 4),
                "threshold": round(threshold, 4),
                "risk": round(risk_score),
                "x": round(float(pca_point[0][0]), 3), 
                "y": round(float(pca_point[0][1]), 3)
            }
            
        except Exception as e:
            print(f"Verification Error: {e}")
            return {"status": "Error", "msg": str(e), "risk": 0}