import json
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
from typing import List, Dict

class PPEMqttPublisher:
    def __init__(self, broker: str = "localhost", port: int = 1883, topic: str = "factory/ppe_violations"):
        self.broker = broker
        self.port = port
        self.topic = topic
        
        self.client = mqtt.Client(protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        
        # Track consecutive violations per worker
        # worker_id -> {'count': int, 'missing_equipment': list, 'confidence': float}
        self.violation_tracker: Dict[str, Dict] = {}
        self.VIOLATION_THRESHOLD = 3
        
        # Connect to broker non-blocking if possible
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
        except Exception as e:
            print(f"Warning: Could not connect to MQTT broker {broker}:{port}. {e}")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to MQTT broker at {self.broker}:{self.port}")
        else:
            print(f"Failed to connect to MQTT broker, return code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        print("Disconnected from MQTT broker")

    def process_worker_state(self, worker_id: str, is_compliant: bool, missing_equipment: List[str] = None, confidence_score: float = 0.0):
        """
        Updates the tracker and publishes a violation if the threshold is met.
        """
        if is_compliant:
            # Reset the counter if the worker is compliant
            if worker_id in self.violation_tracker:
                del self.violation_tracker[worker_id]
            return
        
        # Worker is in violation
        if worker_id not in self.violation_tracker:
            self.violation_tracker[worker_id] = {
                'count': 1,
                'missing_equipment': missing_equipment or [],
                'confidence': confidence_score
            }
        else:
            self.violation_tracker[worker_id]['count'] += 1
            # Update with latest equipment list and confidence
            self.violation_tracker[worker_id]['missing_equipment'] = missing_equipment or []
            self.violation_tracker[worker_id]['confidence'] = confidence_score

        # Check if threshold is exceeded
        if self.violation_tracker[worker_id]['count'] > self.VIOLATION_THRESHOLD:
            self._publish_violation(worker_id)
            # Reset or keep high? Let's reset so we don't spam every frame, or set count to threshold
            # Setting it to 0 means it will wait 3 more frames to send again.
            self.violation_tracker[worker_id]['count'] = 0

    def _publish_violation(self, worker_id: str):
        data = self.violation_tracker[worker_id]
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "worker_id": worker_id,
            "status": "VIOLATION",
            "missing_equipment": data['missing_equipment'],
            "confidence_score": data['confidence']
        }
        
        try:
            self.client.publish(self.topic, json.dumps(payload))
            print(f"Published violation alert for {worker_id}: {data['missing_equipment']}")
        except Exception as e:
            print(f"Failed to publish MQTT message: {e}")

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()

if __name__ == "__main__":
    import time
    publisher = PPEMqttPublisher(broker="test.mosquitto.org", port=1883)
    
    # Simulate a worker in violation for 4 frames
    for i in range(4):
        print(f"Frame {i+1}")
        publisher.process_worker_state("Worker_102", False, ["helmet", "safety_hook"], 0.88)
        time.sleep(0.1)
        
    publisher.close()
