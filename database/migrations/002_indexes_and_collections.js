/**
 * Migration 002: Indexes and Collections setup for MongoDB / Mongo Atlas.
 * 
 * Usage:
 *   mongosh "mongodb://localhost:27017/edgevision" database/migrations/002_indexes_and_collections.js
 */

print("Applying Migration 002: Indexes and Collections ...");

db = db.getSiblingDB("edgevision");

// Ensure required collections exist
const collections = [
  "cameras",
  "zones",
  "zone_ppe_rules",
  "ppe_types",
  "detection_events",
  "detected_objects",
  "worker_tracks",
  "violation_events",
  "alert_deliveries",
  "event_images",
  "event_videos",
  "model_versions",
  "inference_metrics",
  "users",
  "roles",
  "audit_logs"
];

collections.forEach(col => {
  if (!db.getCollectionNames().includes(col)) {
    db.createCollection(col);
    print(`Created collection: ${col}`);
  }
});

// Indexes for high throughput real-time queries
db.violation_events.createIndex({ worker_track_id: 1, acknowledgement_status: 1 });
db.violation_events.createIndex({ timestamp: -1 });
db.violation_events.createIndex({ zone_id: 1 });
db.violation_events.createIndex({ camera_id: 1 });

db.cameras.createIndex({ id: 1 }, { unique: true });
db.zones.createIndex({ id: 1 }, { unique: true });
db.worker_tracks.createIndex({ track_id: 1 });
db.audit_logs.createIndex({ timestamp: -1 });

print("Migration 002 completed successfully.");
