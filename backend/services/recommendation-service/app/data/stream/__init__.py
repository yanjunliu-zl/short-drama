"""Real-time Stream Processing — Kafka pipeline + sliding-window aggregation."""
from .kafka_producer import EventProducer, UserEvent
from .feature_aggregator import WindowAggregator, RealTimeFeatureSet
