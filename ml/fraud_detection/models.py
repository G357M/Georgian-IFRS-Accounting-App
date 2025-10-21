import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from typing import Dict, List
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)

class TransactionFraudDetector:
    def __init__(self, model_path='ml/fraud_detection/fraud_detector.joblib', scaler_path='ml/fraud_detection/fraud_scaler.joblib'):
        self.model_path = model_path
        self.scaler_path = scaler_path
        self.isolation_forest = None
        self.scaler = None
        self.feature_columns = [
            'amount_gel', 'hour_of_day', 'day_of_week',
            'days_since_last_transaction', 'amount_zscore',
            'transaction_count_today'
        ]
        self.is_trained = self._load_model()

    def _extract_features(self, transactions: List[Dict]) -> pd.DataFrame:
        """Extracts features for the ML model from raw transaction data."""
        df = pd.DataFrame(transactions)
        
        df['timestamp'] = pd.to_datetime(df['created_at'])
        df['hour_of_day'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        
        # User-specific patterns (simplified for real-time prediction)
        df = df.sort_values(['user_id', 'timestamp'])
        df['days_since_last_transaction'] = df.groupby('user_id')['timestamp'].diff().dt.total_seconds().fillna(0) / (24 * 3600)
        
        # Amount Z-score (requires pre-calculated stats in a real scenario)
        # For this example, we'll use a placeholder mean/std
        user_avg_amount = df.groupby('user_id')['amount_gel'].transform('mean')
        user_std_amount = df.groupby('user_id')['amount_gel'].transform('std').fillna(1)
        df['amount_zscore'] = abs((df['amount_gel'] - user_avg_amount) / user_std_amount)
        
        df['transaction_count_today'] = df.groupby(['user_id', df['timestamp'].dt.date]).cumcount() + 1
        
        return df[self.feature_columns].fillna(0)

    def train(self, training_data: List[Dict]):
        """Trains the model on historical data."""
        logger.info("Starting model training...")
        features_df = self._extract_features(training_data)
        
        self.scaler = StandardScaler()
        features_scaled = self.scaler.fit_transform(features_df)
        
        self.isolation_forest = IsolationForest(contamination=0.05, random_state=42)
        self.isolation_forest.fit(features_scaled)
        
        joblib.dump(self.isolation_forest, self.model_path)
        joblib.dump(self.scaler, self.scaler_path)
        self.is_trained = True
        logger.info("Model training completed and saved.", model_path=self.model_path)

    def _load_model(self) -> bool:
        """Loads a pre-trained model."""
        try:
            self.isolation_forest = joblib.load(self.model_path)
            self.scaler = joblib.load(self.scaler_path)
            logger.info("Pre-trained fraud detection model loaded.")
            return True
        except FileNotFoundError:
            logger.warning("Pre-trained model not found. The model needs to be trained.")
            return False

    def predict_fraud_probability(self, transaction: Dict) -> float:
        """Predicts the fraud probability for a single transaction."""
        if not self.is_trained:
            # In a real system, you might have a default risk score or deny the transaction
            return 0.5 

        features_df = self._extract_features([transaction])
        features_scaled = self.scaler.transform(features_df)
        
        anomaly_score = self.isolation_forest.decision_function(features_scaled)[0]
        
        # Normalize the score to a 0-1 probability range
        fraud_probability = max(0, min(1, (1 - anomaly_score) / 2))
        return fraud_probability

class FraudDetectionService:
    def __init__(self, fraud_threshold=0.75):
        self.detector = TransactionFraudDetector()
        self.fraud_threshold = fraud_threshold
        # In a real app, this service would be subscribed to the event bus
        # event_bus.subscribe("TransactionCreated", self.handle_transaction_created_event)

    async def analyze_transaction(self, transaction: Dict) -> Dict:
        """Analyzes a transaction for fraud and returns a risk assessment."""
        fraud_probability = self.detector.predict_fraud_probability(transaction)
        
        risk_level = "low"
        if fraud_probability > self.fraud_threshold:
            risk_level = "high"
        elif fraud_probability > 0.5:
            risk_level = "medium"
        
        result = {
            "transaction_id": transaction.get("id"),
            "fraud_probability": fraud_probability,
            "risk_level": risk_level,
            "requires_manual_review": fraud_probability > self.fraud_threshold,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
        logger.info("Transaction analyzed for fraud", **result)
        return result

    async def handle_transaction_created_event(self, event_data: Dict):
        """Event handler to analyze a transaction when it's created."""
        transaction_data = event_data["event_data"]
        # Add necessary fields for feature extraction
        transaction_data['id'] = event_data['aggregate_id']
        transaction_data['created_at'] = event_data['timestamp']
        transaction_data['user_id'] = event_data['metadata'].get('user_id')
        transaction_data['amount_gel'] = float(transaction_data['total_amount'])

        analysis_result = await self.analyze_transaction(transaction_data)
        
        if analysis_result["requires_manual_review"]:
            # In a real system, this would trigger an alert or a workflow
            logger.warning("High fraud risk detected, flagging for review", **analysis_result)
            # await alert_service.send_fraud_alert(analysis_result)
            # await transaction_service.flag_for_review(analysis_result["transaction_id"])
        
        # Save the analysis result for auditing and reporting
        # await fraud_repo.save_analysis(analysis_result)
